from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Query, Body, Response
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import os
import sys

from universal_parser import extract_transactions_from_bytes

import firebase_admin
from firebase_admin import auth as fb_auth, credentials
from firebase_admin import firestore as fa_firestore

from utils.classify_transaction import finalize_classification, record_learning
from utils.clean_vendor_name import clean_vendor_name

from routes import ai_router, journal_router, vendors_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://lighthouse-iq.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https://([a-z0-9-]+\.)?vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_router)
app.include_router(journal_router)
app.include_router(vendors_router)

def _init_firebase_once():
    try:
        firebase_admin.get_app()
    except ValueError:
        cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH", "/etc/secrets/firebase-service-account.json")
        print(f"[DEBUG] Initializing Firebase Admin with credentials at {cred_path}", file=sys.stderr)
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("[DEBUG] Firebase Admin initialized", file=sys.stderr)

def _db():
    _init_firebase_once()
    client = fa_firestore.client()
    print("[DEBUG] Firestore client initialized (Firebase Admin)", file=sys.stderr)
    return client

def _verify_and_decode(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1].strip()
    _init_firebase_once()
    try:
        decoded = fb_auth.verify_id_token(token, check_revoked=False)
        print(f"[DEBUG] Auth OK for uid={decoded.get('uid')}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] verify_id_token failed: {e}", file=sys.stderr)
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

def _touch_user_profile(db: Any, uid: str, email: str | None):
    try:
        uref = db.collection("users").document(uid)
        uref.set(
            {
                "email": (email or "").lower(),
                "createdAt": fa_firestore.SERVER_TIMESTAMP,
                "updatedAt": fa_firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
    except Exception as e:
        print(f"[WARN] touch profile failed: {e}", file=sys.stderr)

def _delete_query(q: fa_firestore.Query, chunk: int = 450):
    docs = list(q.stream())
    deleted_total = 0
    while docs:
        batch = q._client.batch()
        for d in docs[:chunk]:
            batch.delete(d.reference)
        try:
            batch.commit()
            deleted_total += len(docs[:chunk])
        except Exception as e:
            print(f"[ERROR] Delete batch failed: {e}", file=sys.stderr)
            break
        docs = docs[chunk:]
    print(f"[DEBUG] Delete query removed {deleted_total} docs", file=sys.stderr)

def _server_allowed_accounts() -> List[str]:
    import json
    raw = os.environ.get("ALLOWED_ACCOUNTS_JSON", "").strip()
    if raw:
        try:
            arr = json.loads(raw)
            if isinstance(arr, list):
                return [str(x) for x in arr if x]
        except Exception as e:
            print(f"[WARN] Failed to parse ALLOWED_ACCOUNTS_JSON: {e}", file=sys.stderr)
    return [
        "1000 - Checking Account","1010 - Savings Account","1020 - Petty Cash",
        "1030 - Accounts Receivable","1050 - Inventory","1060 - Fixed Assets",
        "1070 - Accumulated Depreciation","2000 - Accounts Payable","2010 - Credit Card Payables",
        "2040 - Loan Payable","2020 - Payroll Liabilities","2030 - Sales Tax Payable",
        "3000 - Contributions","3010 - Draws","3020 - Retained Earnings",
        "4000 - Product Sales","4010 - Service Income","4020 - Subscription Revenue",
        "4030 - Consulting Income","4040 - Other Revenue","4090 - Refunds and Discounts (Contra-Revenue)",
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

@app.get("/")
def root():
    return {"ok": True}

@app.head("/")
def root_head():
    return Response(status_code=200)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/debug-firestore")
def debug_firestore(authorization: str = Header(None)):
    decoded = _verify_and_decode(authorization)
    db = _db()
    _touch_user_profile(db, decoded["uid"], decoded.get("email"))
    doc = {"ping": True, "ts": fa_firestore.SERVER_TIMESTAMP, "note": "debug ping"}
    ref = db.collection("users").document(decoded["uid"]).collection("debug_pings").document()
    try:
        ref.set(doc)
        print(f"[DEBUG] Wrote debug ping doc {ref.id} for uid={decoded['uid']}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] debug-firestore write failed: {e}", file=sys.stderr)
        raise
    return {"ok": True, "docId": ref.id}

@app.post("/parse-and-persist")
async def parse_and_persist(
    authorization: str = Header(None),
    file: UploadFile = File(...),
    autoClassify: bool = Query(True)
):
    decoded = _verify_and_decode(authorization)
    db = _db()
    _touch_user_profile(db, decoded["uid"], decoded.get("email"))
    uid = decoded["uid"]

    pdf_bytes = await file.read()
    rows, meta = extract_transactions_from_bytes(pdf_bytes)
    source = str(meta.get("source_account") or meta.get("source") or "Unknown")
    print(f"[DEBUG] Parsed {len(rows)} rows from {file.filename} (source='{source}') for uid={uid}", file=sys.stderr)

    uref = db.collection("users").document(uid)
    upref = uref.collection("uploads").document()
    upload_id = upref.id

    created: List[Dict[str, Any]] = []
    batch = db.batch()
    batch.set(upref, {
        "fileName": file.filename,
        "source": source,
        "transactionCount": int(len(rows or [])),
        "status": "ready",
        "createdAt": fa_firestore.SERVER_TIMESTAMP,
        "updatedAt": fa_firestore.SERVER_TIMESTAMP,
    })

    tcol = uref.collection("transactions")
    for r in rows or []:
        memo = str(r.get("memo") or r.get("memo_raw") or r.get("memo_clean") or "")
        date = str(r.get("date") or "")
        amount = float(r.get("amount") or 0.0)
        acct = str(r.get("account") or "")
        src = str(r.get("source") or source)
        docref = tcol.document()
        batch.set(docref, {
            "date": date,
            "dateKey": _parse_date_key(date),
            "memo": memo,
            "amount": amount,
            "account": acct,
            "source": src,
            "uploadId": upload_id,
            "fileName": file.filename,
            "createdAt": fa_firestore.SERVER_TIMESTAMP,
        })
        created.append({"id": docref.id, "memo": memo, "amount": amount, "source": src})

    try:
        batch.commit()
        print(f"[DEBUG] Batch committed with {len(created)} transaction docs for uid={uid}, uploadId={upload_id}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Firestore commit failed (parse-and-persist): {e}", file=sys.stderr)
        raise

    if autoClassify and created:
        allowed = _server_allowed_accounts()
        batch2 = db.batch()
        for it in created:
            vendor_key = clean_vendor_name(it["memo"]).lower()
            account, via = finalize_classification(
                db=db,
                uid=uid,
                vendor_key=vendor_key,
                memo=it["memo"],
                amount=float(it["amount"] or 0.0),
                source=str(it["source"] or ""),
                allowed_accounts=allowed
            )
            record_learning(db=db, vendor_key=vendor_key, account=account, uid=uid)
            try:
                batch2.update(tcol.document(it["id"]), {"account": account, "classificationSource": via})
            except Exception as e:
                print(f"[WARN] classification update skipped for doc {it['id']}: {e}", file=sys.stderr)
        try:
            batch2.commit()
            print(f"[DEBUG] Classification updates committed for {len(created)} docs (uid={uid})", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Classification commit failed: {e}", file=sys.stderr)

    return {
        "ok": True,
        "uploadId": upload_id,
        "fileName": file.filename,
        "source": source,
        "transactionCount": len(rows or []),
        "autoClassified": bool(autoClassify),
    }

@app.post("/replace-upload")
async def replace_upload(
    authorization: str = Header(None),
    uploadId: str = Query(..., min_length=1),
    file: UploadFile = File(...),
    autoClassify: bool = Query(True)
):
    decoded = _verify_and_decode(authorization)
    db = _db()
    _touch_user_profile(db, decoded["uid"], decoded.get("email"))
    uid = decoded["uid"]

    pdf_bytes = await file.read()
    rows, meta = extract_transactions_from_bytes(pdf_bytes)
    source = str(meta.get("source_account") or meta.get("source") or "Unknown")
    print(f"[DEBUG] Replace uploadId={uploadId}: parsed {len(rows)} rows from {file.filename} (source='{source}')", file=sys.stderr)

    uref = db.collection("users").document(uid)
    upref = uref.collection("uploads").document(uploadId)

    if not upref.get().exists:
        print(f"[ERROR] replace-upload: uploadId not found ({uploadId})", file=sys.stderr)
        raise HTTPException(status_code=404, detail="Upload not found")

    _delete_query(uref.collection("transactions").where("uploadId", "==", uploadId))

    created: List[Dict[str, Any]] = []
    batch = db.batch()
    tcol = uref.collection("transactions")
    for r in rows or []:
        memo = str(r.get("memo") or r.get("memo_raw") or r.get("memo_clean") or "")
        date = str(r.get("date") or "")
        amount = float(r.get("amount") or 0.0)
        acct = str(r.get("account") or "")
        src = str(r.get("source") or source)
        docref = tcol.document()
        batch.set(docref, {
            "date": date,
            "dateKey": _parse_date_key(date),
            "memo": memo,
            "amount": amount,
            "account": acct,
            "source": src,
            "uploadId": uploadId,
            "fileName": file.filename,
            "createdAt": fa_firestore.SERVER_TIMESTAMP,
        })
        created.append({"id": docref.id, "memo": memo, "amount": amount, "source": src})

    batch.update(upref, {
        "fileName": file.filename,
        "source": source,
        "transactionCount": int(len(rows or [])),
        "status": "ready",
        "updatedAt": fa_firestore.SERVER_TIMESTAMP,
    })
    try:
        batch.commit()
        print(f"[DEBUG] Replace commit wrote {len(created)} docs (uid={uid}, uploadId={uploadId})", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Replace commit failed: {e}", file=sys.stderr)
        raise

    if autoClassify and created:
        allowed = _server_allowed_accounts()
        batch2 = db.batch()
        for it in created:
            vendor_key = clean_vendor_name(it["memo"]).lower()
            account, via = finalize_classification(
                db=db,
                uid=uid,
                vendor_key=vendor_key,
                memo=it["memo"],
                amount=float(it["amount"] or 0.0),
                source=str(it["source"] or ""),
                allowed_accounts=allowed
            )
            record_learning(db=db, vendor_key=vendor_key, account=account, uid=uid)
            try:
                batch2.update(tcol.document(it["id"]), {"account": account, "classificationSource": via})
            except Exception as e:
                print(f"[WARN] classification update skipped for doc {it['id']}: {e}", file=sys.stderr)
        try:
            batch2.commit()
            print(f"[DEBUG] Replace classification commit OK ({len(created)} docs)", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Replace classification commit failed: {e}", file=sys.stderr)

    return {
        "ok": True,
        "uploadId": uploadId,
        "fileName": file.filename,
        "source": source,
        "transactionCount": len(rows or []),
        "autoClassified": bool(autoClassify),
    }

@app.post("/delete-upload")
def delete_upload(authorization: str = Header(None), uploadId: str = Query(..., min_length=1)):
    decoded = _verify_and_decode(authorization)
    db = _db()
    _touch_user_profile(db, decoded["uid"], decoded.get("email"))
    uid = decoded["uid"]
    uref = db.collection("users").document(uid)
    _delete_query(uref.collection("transactions").where("uploadId", "==", uploadId))
    uref.collection("uploads").document(uploadId).delete()
    print(f"[DEBUG] Deleted uploadId={uploadId} for uid={uid}", file=sys.stderr)
    return {"ok": True, "deletedUploadId": uploadId}

@app.post("/delete-all-uploads")
def delete_all_uploads(authorization: str = Header(None)):
    decoded = _verify_and_decode(authorization)
    _require_recent_login(decoded, max_age_sec=180)
    db = _db()
    _touch_user_profile(db, decoded["uid"], decoded.get("email"))
    uid = decoded["uid"]
    uref = db.collection("users").document(uid)
    _delete_query(uref.collection("transactions").where("uploadId", ">=", ""))
    _delete_query(uref.collection("uploads").where("fileName", ">=", ""))
    print(f"[DEBUG] Cleared all uploads/transactions for uid={uid}", file=sys.stderr)
    return {"ok": True}

@app.post("/delete-legacy-transactions")
def delete_legacy_transactions(authorization: str = Header(None)):
    decoded = _verify_and_decode(authorization)
    _require_recent_login(decoded, max_age_sec=180)
    db = _db()
    _touch_user_profile(db, decoded["uid"], decoded.get("email"))
    uid = decoded["uid"]
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
    print(f"[DEBUG] Deleted {deleted} legacy transactions for uid={uid}", file=sys.stderr)
    return {"ok": True, "deleted": deleted}

@app.get("/transactions")
def list_transactions(authorization: str = Header(None), limit: int = Query(1000, ge=1, le=5000)):
    decoded = _verify_and_decode(authorization)
    db = _db()
    _touch_user_profile(db, decoded["uid"], decoded.get("email"))
    uid = decoded["uid"]
    uref = db.collection("users").document(uid)
    q = uref.collection("transactions").order_by("createdAt", direction=fa_firestore.Query.DESCENDING).limit(limit)
    out = []
    for d in q.stream():
        doc = d.to_dict() or {}
        doc["id"] = d.id
        out.append(doc)
    print(f"[DEBUG] list_transactions returning {len(out)} docs for uid={uid}", file=sys.stderr)
    return {"ok": True, "transactions": out}

@app.get("/uploads")
def list_uploads(authorization: str = Header(None), limit: int = Query(500, ge=1, le=2000)):
    decoded = _verify_and_decode(authorization)
    db = _db()
    _touch_user_profile(db, decoded["uid"], decoded.get("email"))
    uid = decoded["uid"]
    uref = db.collection("users").document(uid)
    q = uref.collection("uploads").order_by("createdAt", direction=fa_firestore.Query.DESCENDING).limit(limit)
    out = []
    for d in q.stream():
        doc = d.to_dict() or {}
        doc["id"] = d.id
        out.append(doc)
    print(f"[DEBUG] list_uploads returning {len(out)} rows for uid={uid}", file=sys.stderr)
    return {"ok": True, "uploads": out}

def _normalize_allowed(accounts: Any) -> List[str]:
    if not accounts:
        return []
    return [str(a) for a in accounts if a]

@app.post("/classify-batch")
def classify_batch(payload: Dict[str, Any] = Body(...), authorization: str = Header(None)):
    decoded = _verify_and_decode(authorization)
    db = _db()
    _touch_user_profile(db, decoded["uid"], decoded.get("email"))
    uid = decoded["uid"]

    items_in = payload.get("items") or []
    allowed_accounts = _normalize_allowed(payload.get("allowedAccounts")) or _server_allowed_accounts()
    persist = bool(payload.get("persist") or False)

    print(f"[DEBUG] classify-batch items={len(items_in)} persist={persist} uid={uid}", file=sys.stderr)

    memo_cache: Dict[str, str] = {}
    out_items = []

    batch = db.batch() if persist else None
    uref = db.collection("users").document(uid)
    tcol = uref.collection("transactions")

    for it in items_in:
        item_id = str(it.get("id") or "")
        memo = str(it.get("memo") or "")
        amount = float(it.get("amount") or 0.0)
        source = str(it.get("source") or "")

        vendor_key = memo_cache.get(memo)
        if not vendor_key:
            vendor_key = clean_vendor_name(memo).lower()
            memo_cache[memo] = vendor_key

        account, via = finalize_classification(
            db=db,
            uid=uid,
            vendor_key=vendor_key,
            memo=memo,
            amount=amount,
            source=source,
            allowed_accounts=allowed_accounts
        )
        record_learning(db=db, vendor_key=vendor_key, account=account, uid=uid)

        if persist and item_id:
            try:
                batch.update(tcol.document(item_id), {"account": account, "classificationSource": via})
            except Exception as e:
                print(f"[WARN] classify-batch update failed for {item_id}: {e}", file=sys.stderr)

        out_items.append({"id": item_id, "account": account, "via": via})

    if persist and batch is not None:
        try:
            batch.commit()
            print(f"[DEBUG] classify-batch commit OK for {len(out_items)} items", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] classify-batch commit failed: {e}", file=sys.stderr)

    return {"ok": True, "items": out_items}
