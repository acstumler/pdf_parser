import os
import json
import time
import random
import asyncio
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore
from openai import OpenAI

# -------- Firebase Admin bootstrap (service account via env) --------
if not firebase_admin._apps:
    firebase_key_str = os.getenv("FIREBASE_KEY_JSON")
    if not firebase_key_str:
        raise RuntimeError("FIREBASE_KEY_JSON not set")
    cred = credentials.Certificate(json.loads(firebase_key_str))
    firebase_admin.initialize_app(cred)

db = firestore.client()

# -------- OpenAI client --------
openai_client = OpenAI(
    base_url=os.getenv("OPENAI_API_BASE") or None,
    api_key=os.getenv("OPENAI_API_KEY"),
)

# -------- COA list (imported from project module) --------
# Must exist in your codebase as a python list[str] of legal account names
from chart_of_accounts import chart_of_accounts  # noqa: E402


def _slug_vendor(memo: str) -> str:
    cleaned = "".join(c.lower() if c.isalnum() or c.isspace() else " " for c in memo)
    return " ".join(cleaned.split())[:80]


def _not_source_account(proposed: str, source: str) -> bool:
    return proposed.strip().lower() != source.strip().lower()


async def _ai_fallback(memo: str, amount: float, source: str, source_type: Optional[str]) -> str:
    coa_text = "\n- " + "\n- ".join(chart_of_accounts)
    rules = ""

    if source_type == "Credit Card":
        rules = (
            "Interpret amounts on credit card statements:\n"
            "- Positive = charges (expenses).\n"
            "- Negative = refunds or payments.\n"
            "Return the purpose account (Meals, Supplies, Refund Income, etc.), never the source card.\n"
        )
    elif source_type == "Bank":
        rules = (
            "Interpret amounts on bank statements:\n"
            "- Negative = payments/expenses/draws.\n"
            "- Positive = income/refunds/contributions.\n"
            "Return the purpose account (Revenue, Owner Contribution, Expense, etc.), never the bank itself.\n"
        )

    prompt = f"""
You classify one transaction into the correct account from the Chart of Accounts.
Return ONLY the account name (exact match), nothing else.

Source Type: {source_type or 'Unknown'}
Memo: "{memo}"
Amount: {amount}
Source Account (offset, never choose): {source}

If unclear, choose: 7090 - Uncategorized Expense

Chart of Accounts:
{coa_text}
""".strip()

    # Light throttling + simple retry
    await asyncio.sleep(0.2)
    for attempt in range(3):
        try:
            resp = await openai_client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                timeout=20,
            )
            candidate = resp.choices[0].message.content.strip()
            return candidate if _not_source_account(candidate, source) else "7090 - Uncategorized Expense"
        except Exception as e:
            if attempt < 2 and any(s in str(e).lower() for s in ("429", "timeout", "502", "500")):
                time.sleep((2 ** attempt) + random.uniform(0, 0.5))
                continue
            return "7090 - Uncategorized Expense"


def _get_user_mem(uid: str, slug: str) -> Optional[str]:
    doc = db.collection("users").document(uid).collection("vendorMemory").document(slug).get()
    if doc.exists:
        return doc.to_dict().get("account")
    return None


def _get_global_mem(slug: str) -> Optional[str]:
    doc = db.collection("globalVendorMemory").document(slug).get()
    if doc.exists:
        return doc.to_dict().get("account")
    return None


def _set_user_mem(uid: str, slug: str, account: str) -> None:
    db.collection("users").document(uid).collection("vendorMemory").document(slug).set({"account": account}, merge=True)


async def classify_transaction(
    memo: str,
    amount: float,
    date: str,
    source: str,
    user_id: str,
    source_type: Optional[str] = None,
) -> str:
    slug = _slug_vendor(memo)

    # 1) User memory
    user_hit = _get_user_mem(user_id, slug)
    if user_hit and _not_source_account(user_hit, source):
        return user_hit

    # 2) Global memory
    global_hit = _get_global_mem(slug)
    if global_hit and _not_source_account(global_hit, source):
        return global_hit

    # 3) Local ML (optional—only if model is present)
    try:
        from ml_classifier import classify_memo  # lazy import so service can run without model
        ml_guess = classify_memo(memo)
        if ml_guess and _not_source_account(ml_guess, source):
            return ml_guess
    except Exception:
        pass

    # 4) AI fallback
    ai_guess = await _ai_fallback(memo=memo, amount=amount, source=source, source_type=source_type)
    if not _not_source_account(ai_guess, source):
        ai_guess = "7090 - Uncategorized Expense"

    # 5) Learn to user memory
    try:
        _set_user_mem(user_id, slug, ai_guess)
    except Exception:
        pass

    return ai_guess
