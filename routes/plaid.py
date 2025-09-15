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
    return {
        "ok": True,
        "configured": bool(os.getenv("PLAID_CLIENT_ID") and os.getenv("PLAID_SECRET")),
        "env": env,
        "redirectUriSet": bool(os.getenv("PLAID_REDIRECT_URI")),
        "webhookSet": bool(os.getenv("PLAID_WEBHOOK_URL")),
        "encryptionReady": _enc_ready(),
    }

@router.post("/create-link-token")
def create_link_token(user: Dict[str, Any] = Depends(require_auth)):
    from plaid.model.products import Products
    from plaid.model.country_code import CountryCode
    from plaid.model.link_token_create_request import LinkTokenCreateRequest
    from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
    client = _plaid_client()
    uid = str(user.get("uid") or "")
    kwargs: Dict[str, Any] = dict(
        products=[Products("transactions")],
        client_name="LumiLedger",
        country_codes=[CountryCode("US")],
        language="en",
        user=LinkTokenCreateRequestUser(client_user_id=uid),
    )
    webhook = os.getenv("PLAID_WEBHOOK_URL") or ""
    if webhook:
        kwargs["webhook"] = webhook
    redirect_uri = os.getenv("PLAID_REDIRECT_URI") or ""
    if redirect_uri:
        kwargs["redirect_uri"] = redirect_uri
    req = LinkTokenCreateRequest(**kwargs)
    resp = client.link_token_create(req).to_dict()
    return {"ok": True, "link_token": resp.get("link_token")}

@router.post("/exchange-public-token")
def exchange_public_token(payload: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_auth)):
    from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
    client = _plaid_client()
    public_token = str(payload.get("public_token") or "")
    if not public_token:
        raise HTTPException(status_code=400, detail="missing public_token")
    exchange = client.item_public_token_exchange(ItemPublicTokenExchangeRequest(public_token=public_token)).to_dict()
    access_token = exchange.get("access_token") or ""
    item_id = exchange.get("item_id") or ""
    if not access_token or not item_id:
        raise HTTPException(status_code=502, detail="plaid exchange failed")
    db = _db()
    uid = str(user.get("uid") or "")
    doc = {
        "item_id": item_id,
        "institution": str((payload.get("institution") or {}).get("name") or payload.get("institution_name") or ""),
        "createdAt": fa_firestore.SERVER_TIMESTAMP,
        "updatedAt": fa_firestore.SERVER_TIMESTAMP,
    }
    if _enc_ready():
        try:
            doc["access_token_enc"] = _encrypt_str(access_token)
        except Exception:
            doc["access_token"] = access_token
    else:
        doc["access_token"] = access_token
    db.collection("users").document(uid).collection("plaid_items").document(item_id).set(doc, merge=True)
    return {"ok": True, "item_id": item_id}

@router.get("/items")
def list_items(user: Dict[str, Any] = Depends(require_auth)):
    db = _db()
    uid = str(user.get("uid") or "")
    items = []
    for d in db.collection("users").document(uid).collection("plaid_items").stream():
        rec = d.to_dict() or {}
        items.append({
            "item_id": d.id,
            "institution": rec.get("institution") or "",
            "createdAt": rec.get("createdAt"),
            "updatedAt": rec.get("updatedAt"),
        })
    return {"ok": True, "items": items}

@router.post("/sync")
def sync_transactions(user: Dict[str, Any] = Depends(require_auth)):
    from plaid.model.accounts_get_request import AccountsGetRequest
    from plaid.model.transactions_sync_request import TransactionsSyncRequest
    client = _plaid_client()
    db = _db()
    uid = str(user.get("uid") or "")
    uref = db.collection("users").document(uid)
    items = list(uref.collection("plaid_items").stream())
    if not items:
        return {"ok": True, "synced": 0, "modified": 0, "removed": 0}
    total_added = 0
    total_modified = 0
    total_removed = 0
    allowed = _server_allowed_accounts()
    for d in items:
        rec = d.to_dict() or {}
        try:
            enc = rec.get("access_token_enc")
            access_token = _decrypt_to_str(enc) if enc else str(rec.get("access_token") or "")
        except Exception:
            continue
        if not access_token:
            continue
        new_cursor = rec.get("cursor") or None
        accounts = client.accounts_get(AccountsGetRequest(access_token=access_token)).to_dict()
        acct_map: Dict[str, str] = {}
        acct_type_map: Dict[str, str] = {}
        for a in accounts.get("accounts") or []:
            acc_id = str(a.get("account_id") or "")
            name = str(a.get("name") or a.get("official_name") or "Account")
            mask = str(a.get("mask") or "")
            acct_map[acc_id] = f"{name} ****{mask}" if mask else name
            typ = (a.get("type") or "").lower().strip()
            if typ == "credit":
                acct_type_map[acc_id] = "card"
            elif typ == "loan":
                acct_type_map[acc_id] = "loan"
            else:
                acct_type_map[acc_id] = "bank"
        has_more = True
        while has_more:
            req_kwargs = {"access_token": access_token}
            if isinstance(new_cursor, str) and new_cursor:
                req_kwargs["cursor"] = new_cursor
            resp = client.transactions_sync(TransactionsSyncRequest(**req_kwargs)).to_dict()
            new_cursor = resp.get("next_cursor") or new_cursor
            has_more = bool(resp.get("has_more"))
            added = resp.get("added") or []
            modified = resp.get("modified") or []
            removed = resp.get("removed") or []
            if added:
                batch = db.batch()
                classify = db.batch()
                for tx in added:
                    plaid_tx_id = str(tx.get("transaction_id") or "")
                    if not plaid_tx_id:
                        continue
                    acc_id = str(tx.get("account_id") or "")
                    src = acct_map.get(acc_id) or "Plaid Account"
                    src_type = acct_type_map.get(acc_id, "bank")
                    memo = str(tx.get("name") or tx.get("merchant_name") or tx.get("authorized_description") or tx.get("original_description") or "").strip()
                    amount = float(tx.get("amount") or 0.0)
                    date = _mmddyyyy(str(tx.get("date") or ""))
                    date_key = date.replace("/", "")
                    disp = compute_display_amount(db=db, uid=uid, amount=amount, source_type=src_type, source=src, date=date, date_key=date_key)
                    doc_id = f"plaid:{d.id}:{plaid_tx_id}"
                    docref = uref.collection("transactions").document(doc_id)
                    batch.set(docref, {"plaidTxId": plaid_tx_id, "plaidAccountId": acc_id, "itemId": d.id, "date": date, "dateKey": date_key, "memo": memo, "amount": amount, "displayAmount": disp, "account": "", "source": src, "sourceType": src_type, "uploadId": f"plaid:{d.id}", "fileName": "Plaid", "createdAt": fa_firestore.SERVER_TIMESTAMP, "updatedAt": fa_firestore.SERVER_TIMESTAMP}, merge=True)
                    vendor_key = clean_vendor_name(memo).lower()
                    account, via = finalize_classification(db=db, uid=uid, vendor_key=vendor_key, memo=memo, amount=amount, source=src, allowed_accounts=allowed)
                    record_learning(db=db, vendor_key=vendor_key, account=account, uid=uid)
                    classify.set(docref, {"account": account, "classificationSource": via}, merge=True)
                try:
                    batch.commit(); classify.commit()
                except Exception:
                    pass
                try:
                    for tx in added:
                        plaid_tx_id = str(tx.get("transaction_id") or "")
                        if plaid_tx_id:
                            pair_on_ingest(db, uid, f"plaid:{d.id}:{plaid_tx_id}")
                except Exception:
                    pass
                total_added += len(added)
            if modified:
                batch = db.batch()
                classify = db.batch()
                for tx in modified:
                    plaid_tx_id = str(tx.get("transaction_id") or "")
                    if not plaid_tx_id:
                        continue
                    acc_id = str(tx.get("account_id") or "")
                    src = acct_map.get(acc_id) or "Plaid Account"
                    src_type = acct_type_map.get(acc_id, "bank")
                    memo = str(tx.get("name") or tx.get("merchant_name") or tx.get("authorized_description") or tx.get("original_description") or "").strip()
                    amount = float(tx.get("amount") or 0.0)
                    date = _mmddyyyy(str(tx.get("date") or ""))
                    date_key = date.replace("/", "")
                    disp = compute_display_amount(db=db, uid=uid, amount=amount, source_type=src_type, source=src, date=date, date_key=date_key)
                    doc_id = f"plaid:{d.id}:{plaid_tx_id}"
                    docref = uref.collection("transactions").document(doc_id)
                    batch.set(docref, {"plaidTxId": plaid_tx_id, "plaidAccountId": acc_id, "itemId": d.id, "date": date, "dateKey": date_key, "memo": memo, "amount": amount, "displayAmount": disp, "source": src, "sourceType": src_type, "updatedAt": fa_firestore.SERVER_TIMESTAMP}, merge=True)
                    vendor_key = clean_vendor_name(memo).lower()
                    account, via = finalize_classification(db=db, uid=uid, vendor_key=vendor_key, memo=memo, amount=amount, source=src, allowed_accounts=allowed)
                    record_learning(db=db, vendor_key=vendor_key, account=account, uid=uid)
                    classify.set(docref, {"account": account, "classificationSource": via}, merge=True)
                try:
                    batch.commit(); classify.commit()
                except Exception:
                    pass
                try:
                    for tx in modified:
                        plaid_tx_id = str(tx.get("transaction_id") or "")
                        if plaid_tx_id:
                            pair_on_ingest(db, uid, f"plaid:{d.id}:{plaid_tx_id}")
                except Exception:
                    pass
                total_modified += len(modified)
            if removed:
                batch = db.batch()
                for r in removed:
                    rid = str(r.get("transaction_id") or "")
                    if not rid: 
                        continue
                    doc_id = f"plaid:{d.id}:{rid}"
                    batch.delete(uref.collection("transactions").document(doc_id))
                try:
                    batch.commit()
                except Exception:
                    pass
                total_removed += len(removed)
        uref.collection("plaid_items").document(d.id).set({"cursor": new_cursor, "updatedAt": fa_firestore.SERVER_TIMESTAMP}, merge=True)
    return {"ok": True, "synced": int(total_added), "modified": int(total_modified), "removed": int(total_removed)}

@router.post("/clear-item-transactions")
def clear_item_transactions(payload: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_auth)):
    db = _db()
    uid = str(user.get("uid") or "")
    item_id = str(payload.get("item_id") or "").strip()
    if not item_id:
        raise HTTPException(status_code=400, detail="missing item_id")
    uref = db.collection("users").document(uid)
    docs = list(uref.collection("transactions").where("itemId", "==", item_id).stream())
    start = f"plaid:{item_id}"; end = f"plaid:{item_id}:\uf8ff"
    docs += list(uref.collection("transactions").where("uploadId", ">=", start).where("uploadId", "<=", end).stream())
    seen, uniq = set(), []
    for d in docs:
        if d.id in seen: continue
        seen.add(d.id); uniq.append(d)
    deleted = 0
    while uniq:
        batch = db.batch()
        chunk = uniq[:450]
        for d in chunk: batch.delete(d.reference)
        try: batch.commit(); deleted += len(chunk)
        except Exception: break
        uniq = uniq[450:]
    return {"ok": True, "deleted": int(deleted)}

@router.post("/clear-all-linked-transactions")
def clear_all_linked_transactions(user: Dict[str, Any] = Depends(require_auth)):
    db = _db()
    uid = str(user.get("uid") or "")
    uref = db.collection("users").document(uid)
    docs = list(uref.collection("transactions").where("uploadId", ">=", "plaid:").where("uploadId", "<=", "plaid:\uf8ff").stream())
    deleted = 0
    while docs:
        batch = db.batch()
        chunk = docs[:450]
        for d in chunk: batch.delete(d.reference)
        try: batch.commit(); deleted += len(chunk)
        except Exception: break
        docs = docs[450:]
    return {"ok": True, "deleted": int(deleted)}

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
    pref = uref.collection("plaid_items").document(item_id_in)
    snap = pref.get()
    targets: List[fa_firestore.DocumentSnapshot] = [snap] if snap.exists else list(uref.collection("plaid_items").where("item_id","==",item_id_in).stream())
    if not targets:
        return {"ok": True, "removed": False, "deletedTransactions": False}
    removed_any = False; deleted_tx_total = 0
    for s in targets:
        rec = s.to_dict() or {}; doc_id = s.id
        try:
            tok = _decrypt_to_str(rec["access_token_enc"]) if "access_token_enc" in rec else rec.get("access_token") or ""
            if tok:
                try: client.item_remove(ItemRemoveRequest(access_token=tok)); removed_any = True
                except Exception: pass
        except Exception: pass
        try: s.reference.delete()
        except Exception: pass
        if delete_tx:
            q1 = uref.collection("transactions").where("itemId","==",doc_id)
            docs = list(q1.stream())
            start=f"plaid:{doc_id}"; end=f"plaid:{doc_id}:\uf8ff"
            docs += list(uref.collection("transactions").where("uploadId",">=",start).where("uploadId","<=",end).stream())
            seen=set(); uniq=[]
            for d in docs:
                if d.id in seen: continue
                seen.add(d.id); uniq.append(d)
            while uniq:
                batch = db.batch()
                chunk = uniq[:450]
                for d in chunk: batch.delete(d.reference)
                try: batch.commit(); deleted_tx_total += len(chunk)
                except Exception: break
                uniq = uniq[450:]
    return {"ok": True, "removed": bool(removed_any), "deletedTransactions": bool(delete_tx), "deletedCount": int(deleted_tx_total)}

@router.post("/dedupe")
def dedupe_plaid(user: Dict[str, Any] = Depends(require_auth)):
    db = _db()
    uid = str(user.get("uid") or "")
    uref = db.collection("users").document(uid)
    tcol = uref.collection("transactions")
    snaps = list(tcol.stream())
    by_txid: Dict[str, List[Any]] = {}
    for s in snaps:
        rec = s.to_dict() or {}
        txid = str(rec.get("plaidTxId") or "")
        if not txid:
            continue
        by_txid.setdefault(txid, []).append(s)
    deleted = 0
    for txid, group in by_txid.items():
        if len(group) <= 1:
            continue
        group.sort(key=lambda s: (s.update_time, s.create_time))
        keep = group[-1]
        for s in group[:-1]:
            try:
                s.reference.delete(); deleted += 1
            except Exception:
                pass
    return {"ok": True, "deleted": int(deleted)}
