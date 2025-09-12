from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Query, Body, Response
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import os, json
from universal_parser import extract_transactions_from_bytes
import firebase_admin
from firebase_admin import auth as fb_auth, credentials
from firebase_admin import firestore as fa_firestore
from utils.classify_transaction import finalize_classification, record_learning
from utils.clean_vendor_name import clean_vendor_name
from utils.display_amount import compute_display_amount
from routes import ai_router, journal_router, vendors_router, plaid_router, demo_router
from routes.coa import router as coa_router
from routes.transactions_detail import router as transactions_detail_router
from routes.journal_detail import router as journal_detail_router

app = FastAPI()

def _load_allowed_origins() -> List[str]:
    raw = os.environ.get("ALLOWED_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return ["https://lighthouse-iq.vercel.app","http://localhost:5173","http://localhost:3000"]

_ALLOWED_ORIGINS = _load_allowed_origins()
_ALLOW_ORIGIN_REGEX = r"https://.*\.vercel\.app"

app.add_middleware(CORSMiddleware, allow_origins=_ALLOWED_ORIGINS, allow_origin_regex=_ALLOW_ORIGIN_REGEX, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(ai_router)
app.include_router(journal_router)
app.include_router(vendors_router)
app.include_router(plaid_router)
app.include_router(demo_router)
app.include_router(coa_router)
app.include_router(transactions_detail_router)
app.include_router(journal_detail_router)

def _init_firebase_once():
    try:
        firebase_admin.get_app()
    except ValueError:
        cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH", "/etc/secrets/firebase-service-account.json")
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)

def _db():
    _init_firebase_once()
    return fa_firestore.client()

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
    for fmt in ("%m/%d/%Y","%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y%m%d")
        except Exception:
            pass
    return ""

def _touch_user_profile(db: Any, uid: str, email: str | None):
    try:
        uref = db.collection("users").document(uid)
        uref.set({"email": (email or "").lower(),"createdAt": fa_firestore.SERVER_TIMESTAMP,"updatedAt": fa_firestore.SERVER_TIMESTAMP}, merge=True)
    except Exception:
        pass

def _delete_query(q: fa_firestore.Query, chunk: int = 450):
    docs = list(q.stream())
    while docs:
        batch = q._client.batch()
        for d in docs[:chunk]:
            batch.delete(d.reference)
        try:
            batch.commit()
        except Exception:
            break
        docs = docs[chunk:]

def _server_allowed_accounts() -> List[str]:
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

@app.get("/")
def root():
    return {"ok": True}

@app.head("/")
def root_head():
    return Response(status_code=200)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/cors-origins")
def cors_origins():
    return {"allow_origins": _ALLOWED_ORIGINS, "allow_origin_regex": _ALLOW_ORIGIN_REGEX}

@app.post("/parse-and-persist")
async def parse_and_persist(authorization: str = Header(None), file: UploadFile = File(...), autoClassify: bool = Query(True)):
    decoded = _verify_and_decode(authorization)
    db = _db()
    _touch_user_profile(db, decoded["uid"], decoded.get("email"))
    uid = decoded["uid"]
    pdf_bytes = await file.read()
    rows, meta = extract_transactions_from_bytes(pdf_bytes)
    source = str(meta.get("source_account") or meta.get("source") or "Unknown")
    src_type_default = str(meta.get("source_type") or meta.get("source_kind") or "").lower().strip() or "bank"
    uref = db.collection("users").document(uid)
    upref = uref.collection("uploads").document()
    upload_id = upref.id
    created: List[Dict[str, Any]] = []
    batch = db.batch()
    batch.set(upref, {"fileName": file.filename,"source": source,"transactionCount": int(len(rows or [])),"status": "ready","createdAt": fa_firestore.SERVER_TIMESTAMP,"updatedAt": fa_firestore.SERVER_TIMESTAMP})
    tcol = uref.collection("transactions")
    for r in rows or []:
        memo = str(r.get("memo") or r.get("memo_raw") or r.get("memo_clean") or "")
        date = str(r.get("date") or "")
        amount = float(r.get("amount") or 0.0)
        acct = str(r.get("account") or "")
        src = str(r.get("source") or source)
        date_key = _parse_date_key(date)
        row_src_type = str(r.get("sourceType") or src_type_default or "bank")
        disp = compute_display_amount(db=db, uid=uid, amount=amount, source_type=row_src_type, source=src, date=date, date_key=date_key)
        docref = tcol.document()
        batch.set(docref, {"date": date,"dateKey": date_key,"memo": memo,"amount": amount,"displayAmount": disp,"account": acct,"source": src,"sourceType": row_src_type,"uploadId": upload_id,"fileName": file.filename,"createdAt": fa_firestore.SERVER_TIMESTAMP})
        created.append({"id": docref.id, "memo": memo, "amount": amount, "source": src})
    batch.commit()
    if autoClassify and created:
        allowed = _server_allowed_accounts()
        batch2 = db.batch()
        for it in created:
            vendor_key = clean_vendor_name(it["memo"]).lower()
            account, via = finalize_classification(db=db, uid=uid, vendor_key=vendor_key, memo=it["memo"], amount=float(it["amount"] or 0.0), source=str(it["source"] or ""), allowed_accounts=allowed)
            record_learning(db=db, vendor_key=vendor_key, account=account, uid=uid)
            try:
                batch2.update(tcol.document(it["id"]), {"account": account, "classificationSource": via})
            except Exception:
                pass
        try:
            batch2.commit()
        except Exception:
            pass
    return {"ok": True,"uploadId": upload_id,"fileName": file.filename,"source": source,"transactionCount": len(rows or []),"autoClassified": bool(autoClassify)}

@app.post("/replace-upload")
async def replace_upload(authorization: str = Header(None), uploadId: str = Query(..., min_length=1), file: UploadFile = File(...), autoClassify: bool = Query(True)):
    decoded = _verify_and_decode(authorization)
    db = _db()
    _touch_user_profile(db, decoded["uid"], decoded.get("email"))
    uid = decoded["uid"]
    pdf_bytes = await file.read()
    rows, meta = extract_transactions_from_bytes(pdf_bytes)
    source = str(meta.get("source_account") or meta.get("source") or "Unknown")
    src_type_default = str(meta.get("source_type") or meta.get("source_kind") or "").lower().strip() or "bank"
    uref = db.collection("users").document(uid)
    upref = uref.collection("uploads").document(uploadId)
    if not upref.get().exists:
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
        date_key = _parse_date_key(date)
        row_src_type = str(r.get("sourceType") or src_type_default or "bank")
        disp = compute_display_amount(db=db, uid=uid, amount=amount, source_type=row_src_type, source=src, date=date, date_key=date_key)
        docref = tcol.document()
        batch.set(docref, {"date": date,"dateKey": date_key,"memo": memo,"amount": amount,"displayAmount": disp,"account": acct,"source": src,"sourceType": row_src_type,"uploadId": uploadId,"fileName": file.filename,"createdAt": fa_firestore.SERVER_TIMESTAMP})
        created.append({"id": docref.id, "memo": memo, "amount": amount, "source": src})
    batch.update(upref, {"fileName": file.filename,"source": source,"transactionCount": int(len(rows or [])),"status": "ready","updatedAt": fa_firestore.SERVER_TIMESTAMP})
    batch.commit()
    if autoClassify and created:
        allowed = _server_allowed_accounts()
        batch2 = db.batch()
        for it in created:
            vendor_key = clean_vendor_name(it["memo"]).lower()
            account, via = finalize_classification(db=db, uid=uid, vendor_key=vendor_key, memo=it["memo"], amount=float(it["amount"] or 0.0), source=str(it["source"] or ""), allowed_accounts=allowed)
            record_learning(db=db, vendor_key=vendor_key, account=account, uid=uid)
            try:
                batch2.update(tcol.document(it["id"]), {"account": account, "classificationSource": via})
            except Exception:
                pass
        try:
            batch2.commit()
        except Exception:
            pass
    return {"ok": True,"uploadId": uploadId,"fileName": file.filename,"source": source,"transactionCount": len(rows or []),"autoClassified": bool(autoClassify)}

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
    return {"ok": True, "uploads": out}
