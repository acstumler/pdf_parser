from typing import Iterable, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import os

from universal_parser import extract_transactions_from_bytes

import firebase_admin
from firebase_admin import auth as fb_auth
from google.cloud import firestore

# Classification helpers
from utils.classify_transaction import classify_llm, classify_with_memory
from utils.clean_vendor_name import clean_vendor_name

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.environ.get("ALLOWED_ORIGIN", "*"),
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://lighthouse-iq.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------- Firebase utils --------------------- #
def _init_firebase_once():
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()

def _db():
    return firestore.Client()

def _verify_and_decode(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1].strip()
    _init_firebase_once()
    try:
        decoded = fb_auth.verify_id_token(token, check_revoked=False)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not decoded.get("uid"):
        raise HTTPException(status_code=401, detail="Invalid token")
    return decoded

def _require_recent_login(decoded: dict, max_age_sec: int = 180):
    auth_time = decoded.get("auth_time")
    if not isinstance(auth_time, (int, float)):
        raise HTTPException(status_code=401, detail="Recent login required")
    now = int(datetime.now(timezone.utc).timestamp())
    if now - int(auth_time) > max_age_sec:
        raise HTTPException(status_code=401, detail="Recent login required")

def _parse_date_key(s: str) -> str:
    if not s:
        return ""
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y%m%d")
        except Exception:
            pass
    return ""

def _delete_query(q: firestore.Query, chunk: int = 450):
    docs = list(q.stream())
    while docs:
        batch = q._client.batch()
        for d in docs[:chunk]:
            batch.delete(d.reference)
        batch.commit()
        docs = docs[chunk:]

# -------------------------- Health ----------------------------- #
@app.get("/health")
def health():
    return {"ok": True}

# ------------------ Parse & Persist (create) ------------------- #
@app.post("/parse-and-persist")
async def parse_and_persist(authorization: str = Header(None), file: UploadFile = File(...)):
    decoded = _verify_and_decode(authorization)
    uid = decoded["uid"]
    pdf_bytes = await file.read()

    rows, meta = extract_transactions_from_bytes(pdf_bytes)
    source = str(meta.get("source_account") or meta.get("source") or "Unknown")

    db = _db()
    uref = db.collection("users").document(uid)
    upref = uref.collection("uploads").document()   # generate id
    upload_id = upref.id

    batch = db.batch()
    batch.set(upref, {
        "fileName": file.filename,
        "source": source,
        "transactionCount": int(len(rows or [])),
        "status": "ready",
        "createdAt": firestore.SERVER_TIMESTAMP,
        "updatedAt": firestore.SERVER_TIMESTAMP,
    })

    tcol = uref.collection("transactions")
    for r in rows or []:
        memo = str(r.get("memo") or r.get("memo_raw") or r.get("memo_clean") or "")
        date = str(r.get("date") or "")
        amount = float(r.get("amount") or 0.0)
        acct = str(r.get("account") or "")
        src = str(r.get("source") or source)

        batch.set(tcol.document(), {
            "date": date,
            "dateKey": _parse_date_key(date),
            "memo": memo,
            "amount": amount,
            "account": acct,
            "source": src,
            "uploadId": upload_id,
            "fileName": file.filename,
            "createdAt": firestore.SERVER_TIMESTAMP,
        })

    batch.commit()

    return {
        "ok": True,
        "uploadId": upload_id,
        "fileName": file.filename,
        "source": source,
        "transactionCount": len(rows or []),
    }

# ------------------------ Replace upload ----------------------- #
@app.post("/replace-upload")
async def replace_upload(
    authorization: str = Header(None),
    uploadId: str = Query(..., min_length=1),
    file: UploadFile = File(...),
):
    decoded = _verify_and_decode(authorization)
    uid = decoded["uid"]
    pdf_bytes = await file.read()

    rows, meta = extract_transactions_from_bytes(pdf_bytes)
    source = str(meta.get("source_account") or meta.get("source") or "Unknown")

    db = _db()
    uref = db.collection("users").document(uid)
    upref = uref.collection("uploads").document(uploadId)

    if not upref.get().exists:
        raise HTTPException(status_code=404, detail="Upload not found")

    _delete_query(uref.collection("transactions").where("uploadId", "==", uploadId))

    batch = db.batch()
    tcol = uref.collection("transactions")
    for r in rows or []:
        memo = str(r.get("memo") or r.get("memo_raw") or r.get("memo_clean") or "")
        date = str(r.get("date") or "")
        amount = float(r.get("amount") or 0.0)
        acct = str(r.get("account") or "")
        src = str(r.get("source") or source)

        batch.set(tcol.document(), {
            "date": date,
            "dateKey": _parse_date_key(date),
            "memo": memo,
            "amount": amount,
            "account": acct,
            "source": src,
            "uploadId": uploadId,
            "fileName": file.filename,
            "createdAt": firestore.SERVER_TIMESTAMP,
        })

    batch.update(upref, {
        "fileName": file.filename,
        "source": source,
        "transactionCount": int(len(rows or [])),
        "status": "ready",
        "updatedAt": firestore.SERVER_TIMESTAMP,
    })

    batch.commit()

    return {
        "ok": True,
        "uploadId": uploadId,
        "fileName": file.filename,
        "source": source,
        "transactionCount": len(rows or []),
    }

# ------------------------- Delete upload ----------------------- #
@app.post("/delete-upload")
async def delete_upload(authorization: str = Header(None), uploadId: str = Query(..., min_length=1)):
    decoded = _verify_and_decode(authorization)
    uid = decoded["uid"]
    db = _db()
    uref = db.collection("users").document(uid)

    _delete_query(uref.collection("transactions").where("uploadId", "==", uploadId))
    uref.collection("uploads").document(uploadId).delete()

    return {"ok": True, "deletedUploadId": uploadId}

# ---------------------- Delete all uploads --------------------- #
@app.post("/delete-all-uploads")
async def delete_all_uploads(authorization: str = Header(None)):
    decoded = _verify_and_decode(authorization)
    _require_recent_login(decoded, max_age_sec=180)

    uid = decoded["uid"]
    db = _db()
    uref = db.collection("users").document(uid)

    _delete_query(uref.collection("transactions").where("uploadId", ">=", ""))
    _delete_query(uref.collection("uploads").where("fileName", ">=", ""))

    return {"ok": True}

# ---- TEMP: Delete legacy transactions (no uploadId) ---- #
@app.post("/delete-legacy-transactions")
async def delete_legacy_transactions(authorization: str = Header(None)):
    decoded = _verify_and_decode(authorization)
    _require_recent_login(decoded, max_age_sec=180)

    uid = decoded["uid"]
    db = _db()
    uref = db.collection("users").document(uid)

    docs = list(uref.collection("transactions").stream())
    to_delete = [d for d in docs if not (d.to_dict() or {}).get("uploadId")]
    deleted = 0
    while to_delete:
        batch = db.batch()
        chunk = to_delete[:450]
        for d in chunk:
            batch.delete(d.reference)
        batch.commit()
        deleted += len(chunk)
        to_delete = to_delete[450:]

    return {"ok": True, "deleted": deleted}

# --------------------------- READ APIs ------------------------- #
@app.get("/transactions")
def list_transactions(authorization: str = Header(None), limit: int = Query(1000, ge=1, le=5000)):
    uid = _verify_and_decode(authorization)["uid"]
    db = _db()
    uref = db.collection("users").document(uid)
    q = uref.collection("transactions").order_by("createdAt", direction=firestore.Query.DESCENDING).limit(limit)
    out = []
    for d in q.stream():
        doc = d.to_dict() or {}
        doc["id"] = d.id
        out.append(doc)
    return {"ok": True, "transactions": out}

@app.get("/uploads")
def list_uploads(authorization: str = Header(None), limit: int = Query(500, ge=1, le=2000)):
    uid = _verify_and_decode(authorization)["uid"]
    db = _db()
    uref = db.collection("users").document(uid)
    q = uref.collection("uploads").order_by("createdAt", direction=firestore.Query.DESCENDING).limit(limit)
    out = []
    for d in q.stream():
        doc = d.to_dict() or {}
        doc["id"] = d.id
        out.append(doc)
    return {"ok": True, "uploads": out}

# ======================= CLASSIFICATION ======================= #

def _normalize_allowed(accounts: Any) -> List[str]:
    if not accounts:
        return []
    return [str(a) for a in accounts if a]

@app.post("/classify-batch")
def classify_batch(
    payload: Dict[str, Any] = Body(...),
    authorization: str = Header(None)
):
    decoded = _verify_and_decode(authorization)
    uid = decoded["uid"]
    db = _db()

    items_in = payload.get("items") or []
    allowed_accounts = _normalize_allowed(payload.get("allowedAccounts"))

    # Simple in-request caches to avoid duplicate reads
    memo_cache: Dict[str, str] = {}
    user_mem_cache: Dict[str, str] = {}
    global_mem_cache: Dict[str, str] = {}

    out_items = []
    for it in items_in:
        item_id = str(it.get("id") or "")
        memo = str(it.get("memo") or "")
        amount = float(it.get("amount") or 0.0)
        source = str(it.get("source") or "")

        # Canonical vendor key
        vendor_key = memo_cache.get(memo)
        if not vendor_key:
            vendor_key = clean_vendor_name(memo).lower()
            memo_cache[memo] = vendor_key

        # 1) Memory: user → global
        account, via = classify_with_memory(
            db=db,
            uid=uid,
            vendor_key=vendor_key,
            user_mem_cache=user_mem_cache,
            global_mem_cache=global_mem_cache
        )

        # 2) Fallback: AI (LLM) restricted to allowed accounts (if provided)
        if not account:
            account = classify_llm(memo=memo, amount=amount, source=source, allowed_accounts=allowed_accounts)
            via = "ai"

        out_items.append({"id": item_id, "account": account, "via": via})

    return {"ok": True, "items": out_items}

@app.post("/train-vendor")
def train_vendor(
    payload: Dict[str, Any] = Body(...),
    authorization: str = Header(None)
):
    decoded = _verify_and_decode(authorization)
    uid = decoded["uid"]
    db = _db()

    vendor_key = str(payload.get("vendorKey") or "").strip().lower()
    account = str(payload.get("account") or "").strip()

    if not vendor_key or not account:
        raise HTTPException(status_code=400, detail="vendorKey and account required")

    uref = db.collection("users").document(uid)
    vref = uref.collection("vendor_memory").document(vendor_key)
    vref.set({
        "account": account,
        "updatedAt": firestore.SERVER_TIMESTAMP,
    })
    return {"ok": True, "vendorKey": vendor_key, "account": account}
