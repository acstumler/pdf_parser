from typing import Dict, Any, Optional, List
import os, base64
from datetime import datetime
from fastapi import APIRouter, Body, HTTPException, Depends
from firebase_admin import firestore as fa_firestore, credentials, initialize_app, get_app
from .security import require_auth

def _init_firebase_once():
    try:
        get_app()
    except ValueError:
        cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH", "/etc/secrets/firebase-service-account.json")
        cred = credentials.Certificate(cred_path)
        initialize_app(cred)

def _db():
    _init_firebase_once()
    return fa_firestore.client()

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _CRYPTO_AVAILABLE = True
except Exception:
    _CRYPTO_AVAILABLE = False

def _load_key() -> bytes | None:
    k = os.getenv("PLAID_TOKEN_KEY") or ""
    if not k:
        return None
    try:
        raw = base64.urlsafe_b64decode(k)
        if len(raw) == 32:
            return raw
    except Exception:
        pass
    try:
        if len(k) == 64:
            raw = bytes.fromhex(k)
            if len(raw) == 32:
                return raw
    except Exception:
        pass
    return None

def _enc_ready() -> bool:
    return _CRYPTO_AVAILABLE and _load_key() is not None

def _encrypt_str(plaintext: str) -> Dict[str, str]:
    if not _enc_ready():
        raise RuntimeError("Encryption key not configured")
    key = _load_key()
    aes = AESGCM(key)
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plaintext.encode("utf-8"), None)
    return {"nonce": base64.urlsafe_b64encode(nonce).decode(), "ciphertext": base64.urlsafe_b64encode(ct).decode()}

def _decrypt_to_str(enc: Dict[str, Any]) -> str:
    if not _enc_ready():
        raise RuntimeError("Encryption key not configured")
    key = _load_key()
    aes = AESGCM(key)
    nonce = base64.urlsafe_b64decode(str(enc.get("nonce") or ""))
    ct = base64.urlsafe_b64decode(str(enc.get("ciphertext") or ""))
    pt = aes.decrypt(nonce, ct, None)
    return pt.decode("utf-8")

from utils.clean_vendor_name import clean_vendor_name
from utils.classify_transaction import finalize_classification, record_learning
from utils.display_amount import compute_display_amount
from utils.transfer_pairing import pair_on_ingest

def _server_allowed_accounts() -> List[str]:
    import json
    raw = os.environ.get("ALLOWED_ACCOUNTS_JSON", "").strip()
    if raw:
        try:
            arr = json.loads(raw)
            if isinstance(arr, list):
                return [str(x) for x in arr if x]
        except Exception:
            pass
    return [
        "1000 - Checking Account","1010 - Savings Account","1020 - Petty Cash",
        "1030 - Accounts Receivable","1050 - Inventory","1060 - Fixed Assets",
        "1070 - Accumulated Depreciation","2000 - Accounts Payable","2010 - Credit Card Payables",
        "2040 - Loan Payable","2020 - Payroll Liabilities","2030 - Sales Tax Payable",
        "3000 - Contributions","3010 - Draws","3020 - Retained Earnings",
        "4000 - Product Sales","4010 - Service Income","4020 - Subscription Revenue",
        "4030 - Consulting Income","4040 - Other Revenue","4090 - Refunds and Discounts",
        "5000 - Inventory Purchases","5010 - Subcontracted Labor","5020 - Packaging & Shipping Supplies",
        "5030 - Merchant Fees",
        "6000 - Salaries and Wages","6010 - Payroll Taxes","6020 - Employee Benefits",
        "6030 - Independent Contractors","6040 - Bonuses & Commissions","6050 - Workers Compensation Insurance",
        "6060 - Recruiting & Hiring","6100 - Rent or Lease Expense","6110 - Utilities","6120 - Insurance",
        "6130 - Repairs & Maintenance","6140 - Office Supplies","6150 - Telephone & Internet",
        "6200 - Advertising & Promotion","6210 - Social Media & Digital Ads",
        "6220 - Meals & Entertainment","6230 - Client Gifts",
        "6300 - Software Subscriptions","6310 - Bank Fees","6320 - Dues & Licenses","6330 - Postage & Delivery",
        "6400 - Legal Fees","6410 - Accounting & Bookkeeping","6420 - Consulting Fees","6430 - Tax Prep & Advisory",
        "6500 - Travel - Airfare","6510 - Travel - Lodging","6520 - Travel - Meals","6530 - Travel - Other (Taxis, Parking)",
        "8000 - State Income Tax","8010 - Franchise Tax","8020 - Local Business Taxes","8030 - Estimated Tax Payments",
        "7090 - Uncategorized Expense",
    ]

router = APIRouter(prefix="/plaid", tags=["plaid"])

def _mmddyyyy(iso_date: str) -> str:
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d")
        return d.strftime("%m/%d/%Y")
    except Exception:
        return iso_date

def _plaid_client():
    from plaid.api import plaid_api
    from plaid import Configuration, ApiClient
    env = (os.getenv("PLAID_ENV") or "sandbox").lower().strip()
    host = {
        "sandbox": "https://sandbox.plaid.com",
        "development": "https://development.plaid.com",
        "production": "https://production.plaid.com",
    }.get(env, "https://sandbox.plaid.com")
    cfg = Configuration(host=host)
    cfg.api_key["clientId"] = os.getenv("PLAID_CLIENT_ID", "")
    cfg.api_key["secret"] = os.getenv("PLAID_SECRET", "")
    if not cfg.api_key["clientId"] or not cfg.api_key["secret"]:
        raise HTTPException(status_code=503, detail="Plaid not configured yet")
    return plaid_api.PlaidApi(ApiClient(cfg))

@router.get("/status")
def status():
    env = (os.getenv("PLAID_ENV") or "sandbox").lower()
    return {"ok": True, "configured": bool(os.getenv("PLAID_CLIENT_ID") and os.getenv("PLAID_SECRET")), "env": env, "redirectUriSet": bool(os.getenv("PLAID_REDIRECT_URI")), "webhookSet": bool(os.getenv("PLAID_WEBHOOK_URL")), "encryptionReady": _enc_ready()}

@router.get("/items")
def list_items(user: Dict[str, Any] = Depends(require_auth)):
    db = _db()
    uid = str(user.get("uid") or "")
    items = []
    for d in db.collection("users").document(uid).collection("plaid_items").stream():
        rec = d.to_dict() or {}
        items.append({"item_id": d.id, "institution": rec.get("institution") or "", "createdAt": rec.get("createdAt"), "updatedAt": rec.get("updatedAt")})
    return {"ok": True, "items": items}

@router.post("/disconnect")
def disconnect_item(payload: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_auth)):
    from plaid.model.item_remove_request import ItemRemoveRequest
    client = _plaid_client()
    db = _db()
    uid = str(user.get("uid") or "")
    item_id_in = str(payload.get("item_id") or "").strip()
    delete_tx = bool(payload.get("deleteTransactions") or False)
    if not item_id_in:
        raise HTTPException(status_code=400, detail="missing item_id")

    uref = db.collection("users").document(uid)
    # Resolve the item by doc id OR by 'item_id' field
    pref = uref.collection("plaid_items").document(item_id_in)
    snap = pref.get()
    targets: List[fa_firestore.DocumentSnapshot] = []
    if snap.exists:
        targets = [snap]
    else:
        q = uref.collection("plaid_items").where("item_id", "==", item_id_in)
        targets = list(q.stream())

    if not targets:
        return {"ok": True, "removed": False, "deletedTransactions": False}

    removed_any = False
    deleted_tx_total = 0

    for s in targets:
        rec = s.to_dict() or {}
        doc_id = s.id
        try:
            tok = None
            if "access_token_enc" in rec:
                tok = _decrypt_to_str(rec["access_token_enc"])
            else:
                tok = rec.get("access_token") or ""
            if tok:
                try:
                    client.item_remove(ItemRemoveRequest(access_token=tok))
                    removed_any = True
                except Exception:
                    pass
        except Exception:
            pass

        try:
            s.reference.delete()
        except Exception:
            pass

        if delete_tx:
            # Delete by current scheme: itemId == doc_id
            q1 = uref.collection("transactions").where("itemId", "==", doc_id)
            docs = list(q1.stream())
            # Sweep legacy rows keyed by uploadId "plaid:<doc_id>"
            start = f"plaid:{doc_id}"
            end = f"plaid:{doc_id}:\uf8ff"
            q2 = uref.collection("transactions").where("uploadId", ">=", start).where("uploadId", "<=", end)
            docs += list(q2.stream())

            # Deduplicate references
            seen = set()
            uniq = []
            for d in docs:
                if d.id in seen: 
                    continue
                seen.add(d.id)
                uniq.append(d)

            while uniq:
                batch = db.batch()
                chunk = uniq[:450]
                for d in chunk:
                    batch.delete(d.reference)
                try:
                    batch.commit()
                    deleted_tx_total += len(chunk)
                except Exception:
                    break
                uniq = uniq[450:]

    return {"ok": True, "removed": bool(removed_any), "deletedTransactions": bool(delete_tx), "deletedCount": int(deleted_tx_total)}

# The rest of your sync/exchange/create-link-token and clear endpoints remain as in your current file.
