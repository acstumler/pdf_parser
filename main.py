from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Query, Body, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import os, json, uuid, hmac, hashlib, base64, httpx

from universal_parser import extract_transactions_from_bytes
import firebase_admin
from firebase_admin import auth as fb_auth, credentials
from firebase_admin import firestore as fa_firestore

from routes import ai_router, journal_router, vendors_router, plaid_router, demo_router
from routes.coa import router as coa_router
from routes.transactions_detail import router as transactions_detail_router
from routes.journal_detail import router as journal_detail_router

app = FastAPI()

def _load_allowed_origins() -> List[str]:
    raw = os.environ.get("ALLOWED_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "https://lumiledger.vercel.app",
        "https://lighthouse-iq.vercel.app",
        "http://localhost:5173",
        "http://localhost:3000",
    ]

_ALLOWED_ORIGINS = _load_allowed_origins()
_ALLOW_ORIGIN_REGEX = r"https://.*\.vercel\.app"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_origin_regex=_ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

def _verify_and_decode(authorization: Optional[str]) -> dict:
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

@app.get("/")
def root():
    return {"ok": True}

@app.head("/")
def root_head():
    return Response(status_code=200)

@app.get("/health")
def health():
    return {"ok": True}

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

@app.post("/parse-and-persist")
async def parse_and_persist(
    authorization: str = Header(None),
    file: UploadFile = File(...),
    autoClassify: bool = Query(True),
):
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
    batch.set(
        upref,
        {
            "fileName": file.filename,
            "source": source,
            "transactionCount": int(len(rows or [])),
            "status": "ready",
            "createdAt": fa_firestore.SERVER_TIMESTAMP,
            "updatedAt": fa_firestore.SERVER_TIMESTAMP,
        },
    )
    tcol = uref.collection("transactions")
    for r in rows or []:
        memo = str(r.get("memo") or r.get("memo_raw") or r.get("memo_clean") or "")
        date = str(r.get("date") or "")
        amount = float(r.get("amount") or 0.0)
        acct = str(r.get("account") or "")
        src = str(r.get("source") or source)
        date_key = _parse_date_key(date)
        row_src_type = str(r.get("sourceType") or src_type_default or "bank")
        disp = compute_display_amount(db=db, uid=uid, amount=amount, source_type=row_src_type, source=src, date=date, date_key=date_key)  # noqa: F821
        docref = tcol.document()
        batch.set(
            docref,
            {
                "date": date,
                "dateKey": date_key,
                "memo": memo,
                "amount": amount,
                "displayAmount": disp,
                "account": acct,
                "source": src,
                "sourceType": row_src_type,
                "uploadId": upload_id,
                "fileName": file.filename,
                "createdAt": fa_firestore.SERVER_TIMESTAMP,
            },
        )
        created.append({"id": docref.id, "memo": memo, "amount": amount, "source": src})
    batch.commit()
    if autoClassify and created:
        from utils.clean_vendor_name import clean_vendor_name  # noqa: E402
        from utils.classify_transaction import finalize_classification, record_learning  # noqa: E402
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
    autoClassify: bool = Query(True),
):
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
        disp = compute_display_amount(db=db, uid=uid, amount=amount, source_type=row_src_type, source=src, date=date, date_key=date_key)  # noqa: F821
        docref = tcol.document()
        batch.set(
            docref,
            {
                "date": date,
                "dateKey": date_key,
                "memo": memo,
                "amount": amount,
                "displayAmount": disp,
                "account": acct,
                "source": src,
                "sourceType": row_src_type,
                "uploadId": uploadId,
                "fileName": file.filename,
                "createdAt": fa_firestore.SERVER_TIMESTAMP,
            },
        )
        created.append({"id": docref.id, "memo": memo, "amount": amount, "source": src})
    batch.update(
        upref,
        {
            "fileName": file.filename,
            "source": source,
            "transactionCount": int(len(rows or [])),
            "status": "ready",
            "updatedAt": fa_firestore.SERVER_TIMESTAMP,
        },
    )
    batch.commit()
    if autoClassify and created:
        from utils.clean_vendor_name import clean_vendor_name  # noqa: E402
        from utils.classify_transaction import finalize_classification, record_learning  # noqa: E402
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
    return {
        "ok": True,
        "uploadId": uploadId,
        "fileName": file.filename,
        "source": source,
        "transactionCount": len(rows or []),
        "autoClassified": bool(autoClassify),
    }

def _sq_base() -> str:
    env = (os.environ.get("SQUARE_ENV", "sandbox") or "").lower()
    return "https://connect.squareupsandbox.com" if env != "production" else "https://connect.squareup.com"

def _sq_headers() -> Dict[str, str]:
    tok = os.environ.get("SQUARE_ACCESS_TOKEN", "").strip()
    if not tok:
        raise HTTPException(status_code=500, detail="Square access token missing")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

def _sq_return_url(uid: str) -> str:
    base = os.environ.get("SQUARE_CHECKOUT_RETURN_URL", "").strip() or "https://lumiledger.vercel.app/billing/thanks"
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}u={uid}"

async def _get_plan_variation_id(plan_name: str, frequency: str) -> str:
    frequency = frequency.strip().lower()
    target = "monthly" if "month" in frequency else "annual"
    url = f"{_sq_base()}/v2/catalog/list?types=SUBSCRIPTION_PLAN"
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(url, headers=_sq_headers())
        if res.status_code >= 300:
            raise HTTPException(status_code=502, detail=f"Square catalog error: {res.text}")
        payload = res.json() or {}
        objs = payload.get("objects") or []
        for obj in objs:
            if obj.get("type") == "SUBSCRIPTION_PLAN":
                name = ((obj.get("subscription_plan_data") or {}).get("name") or "").strip().lower()
                if name == plan_name.strip().lower():
                    variations = (obj.get("subscription_plan_data") or {}).get("subscription_plan_variations") or []
                    for v in variations:
                        vname = (v.get("name") or "").strip().lower()
                        vid = v.get("id") or v.get("variation_id") or v.get("subscription_plan_variation_id")
                        if vid and (target in vname or vname == target):
                            return str(vid)
    raise HTTPException(status_code=404, detail=f"Plan variation not found for {plan_name} / {frequency}")

@app.post("/billing/checkout-link")
async def create_checkout_link(
    request: Request,
    authorization: str = Header(None),
    body: Dict[str, Any] = Body(...),
):
    decoded = _verify_and_decode(authorization)
    uid = decoded["uid"]
    plan = str(body.get("plan") or "Starter")
    frequency = str(body.get("frequency") or "monthly")
    buyer_email = str(body.get("buyerEmail") or decoded.get("email") or "")
    variation_id = await _get_plan_variation_id(plan, frequency)
    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "subscription_plan_id": variation_id,
        "checkout_options": {"redirect_url": _sq_return_url(uid)},
    }
    if buyer_email:
        payload["pre_populate_buyer_email"] = buyer_email
    url = f"{_sq_base()}/v2/online-checkout/payment-links"
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(url, headers=_sq_headers(), json=payload)
        if res.status_code >= 300:
            raise HTTPException(status_code=502, detail=f"Create payment link failed: {res.text}")
        data = res.json() or {}
        link = ((data.get("payment_link") or {}).get("url")) or ""
        if not link:
            raise HTTPException(status_code=502, detail="Square did not return a payment link")
    db = _db()
    db.collection("users").document(uid).collection("billing").document("intent").set(
        {"plan": plan, "frequency": frequency, "variationId": variation_id, "createdAt": fa_firestore.SERVER_TIMESTAMP},
        merge=True,
    )
    return {"url": link}

def _secure_compare(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    r = 0
    for x, y in zip(a.encode(), b.encode()):
        r |= x ^ y
    return r == 0

def _compute_webhook_signature(signature_key: str, notification_url: str, raw_body: bytes) -> str:
    mac = hmac.new(signature_key.encode("utf-8"), (notification_url + raw_body.decode("utf-8")).encode("utf-8"), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode("utf-8")

@app.post("/webhooks/square")
async def square_webhook(request: Request):
    signature_key = os.environ.get("SQUARE_WEBHOOK_SIGNATURE_KEY", "").strip()
    if not signature_key:
        return Response(status_code=500, content="Missing signature key")
    raw = await request.body()
    notif_url = str(request.url)
    provided = request.headers.get("x-square-hmacsha256-signature") or request.headers.get("x-square-signature") or ""
    expected = _compute_webhook_signature(signature_key, notif_url, raw)
    if not _secure_compare(provided or "", expected or ""):
        return Response(status_code=401, content="Invalid signature")
    evt = {}
    try:
        evt = json.loads(raw.decode("utf-8"))
    except Exception:
        pass
    etype = str(evt.get("type") or "")
    data = evt.get("data") or {}
    obj = data.get("object") or {}
    db = _db()
    if etype.startswith("subscription."):
        sub = obj.get("subscription") or {}
        status = (sub.get("status") or "").lower()
        customer_id = sub.get("customer_id") or ""
        plan_variation_id = sub.get("plan_variation_id") or sub.get("plan_id") or ""
        email = ""
        if customer_id:
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    c = await client.get(f"{_sq_base()}/v2/customers/{customer_id}", headers=_sq_headers())
                    cj = c.json() if c.status_code < 300 else {}
                    email = (cj.get("customer") or {}).get("email_address") or ""
            except Exception:
                pass
        if email:
            q = db.collection("users").where("email", "==", email.lower()).limit(1).stream()
            target_uid = None
            for d in q:
                target_uid = d.id
                break
            if target_uid:
                db.collection("users").document(target_uid).collection("billing").document("status").set(
                    {
                        "status": status,
                        "squareSubscriptionId": sub.get("id") or "",
                        "planVariationId": plan_variation_id,
                        "updatedAt": fa_firestore.SERVER_TIMESTAMP,
                    },
                    merge=True,
                )
    return {"ok": True}

@app.get("/billing/status")
def billing_status(authorization: str = Header(None)):
    decoded = _verify_and_decode(authorization)
    uid = decoded["uid"]
    db = _db()
    ref = db.collection("users").document(uid).collection("billing").document("status")
    doc = ref.get()
    if not doc.exists:
        return {"status": "none"}
    return doc.to_dict() or {"status": "none"}
