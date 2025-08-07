from fastapi import APIRouter, Request
from firebase_admin import firestore
import openai
import os
import time
import random

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

Source Type: {source_type}
Memo: "{memo}"
Amount: {amount}
Source Account: {source}

{rules}

If the memo is unclear or cannot be reasonably interpreted, classify as '7090 - Uncategorized Expense'.

Chart of Accounts:{coa_text}

Respond only with the exact account name. No quotes or explanation.
""".strip()


def classify_with_openai(prompt: str) -> str:
    retries = 3
    for attempt in range(retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                timeout=10,
            )
            return response.choices[0].message.content.strip()
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
    memo = body.get("memo", "")
    amount = body.get("amount", 0)
    source = body.get("source", "")
    user_id = body.get("uid", None)
    source_type = body.get("source_type", "")  # "Credit Card" or "Bank"

    if not source_type:
        return {"classification": "7090 - Uncategorized Expense"}

    normalized = normalize_vendor(memo)

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
    prompt = build_prompt(memo, amount, source, source_type)
    classification = classify_with_openai(prompt)

    # Step 4: Cache into Firebase
    db.collection("vendor_memory").add({
        "vendor": normalized,
        "account": classification,
        "userId": user_id
    })

    return {"classification": classification}
