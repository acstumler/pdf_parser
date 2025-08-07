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
    coa_text = "\n- " + "\n- ".join(chart_of_accounts)
    prompt = f"""
You are a smart accounting assistant.
Given the following transaction, classify it into the most appropriate account from the Chart of Accounts.

Transaction:
- Memo: "{memo}"
- Amount: {amount}
- Source: {source}

Chart of Accounts:{coa_text}

Only reply with the exact account name. Do not explain or include quotes.
""".strip()

    classification = classify_with_openai(prompt)

    # Step 4: Cache into Firebase
    db.collection("vendor_memory").add({
        "vendor": normalized,
        "account": classification,
        "userId": user_id
    })

    return {"classification": classification}
