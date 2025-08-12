# routes/memory_route.py
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import json
import os
import firebase_admin
from firebase_admin import credentials, firestore
from chart_of_accounts import chart_of_accounts

# Initialize Firebase Admin if not already
if not firebase_admin._apps:
    key_json = os.getenv("FIREBASE_KEY_JSON")
    if not key_json:
        raise RuntimeError("FIREBASE_KEY_JSON not set")
    cred = credentials.Certificate(json.loads(key_json))
    firebase_admin.initialize_app(cred)

db = firestore.client()
memory_router = APIRouter()

class RememberBody(BaseModel):
    memo: str
    account: str

def slug_vendor(memo: str) -> str:
    cleaned = "".join(c.lower() if c.isalnum() or c.isspace() else " " for c in memo or "")
    return " ".join(cleaned.split())[:80]

@memory_router.post("/remember-vendor/")
async def remember_vendor(body: RememberBody, request: Request):
    uid = request.headers.get("X-User-ID", "anonymous").strip() or "anonymous"
    memo = (body.memo or "").strip()
    account = (body.account or "").strip()

    if not memo:
        raise HTTPException(status_code=400, detail="memo is required")
    if account not in chart_of_accounts:
        raise HTTPException(status_code=400, detail="account must match Chart of Accounts exactly")

    vendor = slug_vendor(memo)

    db.collection("users").document(uid).collection("vendorMemory").document(vendor).set(
        {"account": account},
        merge=True,
    )

    return {"ok": True, "vendor": vendor, "account": account, "user": uid}
