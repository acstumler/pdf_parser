from fastapi import APIRouter, Request
from firebase_admin import firestore
import openai
import os
import time
import random
import asyncio

from chart_of_accounts import chart_of_accounts
from vendor_map import vendor_map

router = APIRouter()
db = firestore.client()
openai.api_key = os.getenv("OPENAI_API_KEY")
openai.api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")


def normalize_vendor(memo: str) -> str:
    return ' '.join(
        ''.join(c for c in memo.lower() if c.isalnum() or c.isspace()).split()[:3]
    )


def clean_memo(memo: str) -> str:
    return ' '.join(''.join(c for c in memo if c.isprintable()).split())


def should_retry(exception) -> bool:
    return (
        "429" in str(exception)
        or "timeout" in str(exception).lower()
        or "500" in str(exception)
        or "502" in str(exception)
    )


def build_prompt(memo: str, amount: float, source: str, source_type: str) -> str:
    coa_text = "\n- " + "\n- ".join(chart_of_accounts)

    rules = ""

    if source_type == "Credit Card":
        rules = """
Interpret amounts based on a credit card statement:
- Positive amounts represent charges (expenses).
- Negative amounts represent either refunds or payments.

Rules:
- Classify positive amounts as expense accounts.
- Classify negative amounts as refund income (if related to a return) or bank/cash accounts (if a payment).
- Never classify into the credit card account itself. It is the source account and should not be selected.
"""
    elif source_type == "Bank":
        rules = """
Interpret amounts based on a bank statement:
- Negative amounts represent payments, expenses, or owner draws.
- Positive amounts represent income, refunds, or owner contributions.

Rules:
- Classify negative amounts as:
  - Expense accounts (e.g., Meals, Office Supplies),
  - Liability accounts (e.g., credit card payments),
  - Owner Draws (e.g., 3010 - Owner's Draw).
- Classify positive amounts as:
  - Income accounts (e.g., Revenue, Refund Income),
  - Owner Contributions (e.g., 3020 - Owner's Contribution).
- Never classify into the bank account itself. It is the source account and should not be selected.
"""

    return f"""
You are a smart accounting assistant classifying a financial transaction for a bookkeeping system.

Use professional accounting logic to classify the transaction into the most accurate account from the Chart of Accounts.

The "source account" refers to the financial account this transaction came from — such as a credit card (e.g., AMEX 61005) or a bank account (e.g., Chase 1001). It is the offset account in the journal entry and must **never** be used as the classification.

Your task is to return the **other side** of the transaction — the purpose — such as Meals, Supplies, Income, or Transfers.

Source Type: {source_type}
Memo: "{memo}"
Amount: {amount}
Source Account: {source}

{rules}

If the memo is unclear or cannot be reasonably interpreted, classify as '7090 - Uncategorized Expense'.

Chart of Accounts:{coa_text}

Respond only with the exact account name. No quotes or explanation.
""".strip()


async def classify_with_openai(prompt: str, source: str) -> str:
    await asyncio.sleep(0.2)  # Throttle OpenAI calls to avoid 429
    retries = 3
    for attempt in range(retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                timeout=10,
            )
            classification = response.choices[0].message.content.strip()
            if classification.strip() == source.strip():
                return "7090 - Uncategorized Expense"
            return classification
        except Exception as e:
            if attempt < retries - 1 and should_retry(e):
                wait_time = (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(wait_time)
            else:
                print(f"OpenAI error after retrying: {e}")
                return "7090 - Uncategorized Expense"


@router.post("/classify-transaction")
async def classify_transaction(req: Request):
    body = await req.json()
    raw_memo = body.get("memo", "")
    amount = body.get("amount", 0)
    source = body.get("source", "")
    user_id = body.get("uid", None)
    source_type = body.get("source_type", "")  # "Credit Card" or "Bank"

    if not source_type:
        return {"classification": "7090 - Uncategorized Expense"}

    full_memo = clean_memo(raw_memo)
    normalized = normalize_vendor(raw_memo)

    # Step 1: Firebase memory lookup
    query = (
        db.collection("vendor_memory")
        .where("vendor", "==", normalized)
        .where("userId", "in", [None, user_id])
    )
    results = list(query.stream())
    if results:
        return {"classification": results[0].to_dict()["account"]}

    # Step 2: Static vendor map
    if normalized in vendor_map:
        return {"classification": vendor_map[normalized]}

    # Step 3: GPT fallback
    prompt = build_prompt(full_memo, amount, source, source_type)
    classification = await classify_with_openai(prompt, source)

    # Step 4: Cache into Firebase
    db.collection("vendor_memory").add({
        "vendor": normalized,
        "account": classification,
        "userId": user_id
    })

    return {"classification": classification}
