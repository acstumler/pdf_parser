from fastapi import APIRouter, Request
from firebase_admin import firestore
import openai
import os

from chart_of_accounts import chart_of_accounts
from vendor_map import vendor_map  # Static in-memory fallback

router = APIRouter()
db = firestore.client()
openai.api_key = os.getenv("OPENAI_API_KEY")


def normalize_vendor(memo: str) -> str:
    return ' '.join(
        ''.join(c for c in memo.lower() if c.isalnum() or c.isspace()).split()[:3]
    )


@router.post("/classify-transaction")
async def classify_transaction(req: Request):
    body = await req.json()
    memo = body.get("memo", "")
    amount = body.get("amount", 0)
    source = body.get("source", "")
    user_id = body.get("uid", None)

    normalized = normalize_vendor(memo)

    # Step 1: Check Firebase Memory (user-specific or global)
    query = (
        db.collection("vendor_memory")
        .where("vendor", "==", normalized)
        .where("userId", "in", [None, user_id])
    )
    results = list(query.stream())
    if results:
        return {"classification": results[0].to_dict()["account"]}

    # Step 2: Check Static Vendor Map
    if normalized in vendor_map:
        return {"classification": vendor_map[normalized]}

    # Step 3: Fallback to OpenAI GPT
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

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            timeout=10,
        )
        classification = response.choices[0].message.content.strip()

        # Step 4: Cache classification to Firebase
        db.collection("vendor_memory").add({
            "vendor": normalized,
            "account": classification,
            "userId": user_id
        })

        return {"classification": classification}

    except Exception as e:
        print(f"OpenAI error: {e}")
        return {"classification": "7090 - Uncategorized Expense"}
