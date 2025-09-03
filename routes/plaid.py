from typing import Dict, Any
import os
from datetime import datetime
from fastapi import APIRouter, Depends, Body, Header, HTTPException
from .security import require_auth
from firebase_admin import firestore as fa_firestore

def _have_plaid_keys() -> bool:
    return bool(os.getenv("PLAID_CLIENT_ID") and os.getenv("PLAID_SECRET"))

router = APIRouter(prefix="/plaid", tags=["plaid"])

def _db():
    return fa_firestore.client()

def _mmddyyyy(iso_date: str) -> str:
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d")
        return d.strftime("%m/%d/%Y")
    except Exception:
        return iso_date

@router.get("/status")
def status():
    env = (os.getenv("PLAID_ENV") or "sandbox").lower()
    return {
        "ok": True,
        "configured": _have_plaid_keys(),
        "env": env,
        "redirectUriSet": bool(os.getenv("PLAID_REDIRECT_URI")),
        "webhookSet": bool(os.getenv("PLAID_WEBHOOK_URL")),
    }

def _plaid_client():
    if not _have_plaid_keys():
        raise HTTPException(status_code=503, detail="Plaid not configured yet")
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
    return plaid_api.PlaidApi(ApiClient(cfg))

@router.post("/create-link-token")
def create_link_token(user: Dict[str, Any] = Depends(require_auth)):
    if not _have_plaid_keys():
        raise HTTPException(status_code=503, detail="Plaid pending review (no keys yet)")
    from plaid.model.products import Products
    from plaid.model.country_code import CountryCode
    from plaid.model.link_token_create_request import LinkTokenCreateRequest
    from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser

    client = _plaid_client()
    uid = str(user.get("uid") or "")

    # Build the request, only including optional fields when present.
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
def exchange_public_token(
    payload: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_auth),
):
    if not _have_plaid_keys():
        raise HTTPException(status_code=503, detail="Plaid pending review (no keys yet)")
    from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
    client = _plaid_client()
    public_token = str(payload.get("public_token") or "")
    if not public_token:
        raise HTTPException(status_code=400, detail="missing public_token")
    exchange = client.item_public_token_exchange(
        ItemPublicTokenExchangeRequest(public_token=public_token)
    ).to_dict()
    access_token = exchange.get("access_token") or ""
    item_id = exchange.get("item_id") or ""
    if not access_token or not item_id:
        raise HTTPException(status_code=502, detail="plaid exchange failed")
    db = _db()
    uid = str(user.get("uid") or "")
    db.collection("users").document(uid).collection("plaid_items").document(item_id).set(
        {
            "access_token": access_token,
            "item_id": item_id,
            "institution": str((payload.get("institution") or {}).get("name") or payload.get("institution_name") or ""),
            "createdAt": fa_firestore.SERVER_TIMESTAMP,
            "updatedAt": fa_firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )
    return {"ok": True, "item_id": item_id}

@router.post("/sync")
def sync_transactions(user: Dict[str, Any] = Depends(require_auth)):
    if not _have_plaid_keys():
        return {"ok": True, "synced": 0, "pending": True}
    from plaid.model.accounts_get_request import AccountsGetRequest
    from plaid.model.transactions_sync_request import TransactionsSyncRequest
    client = _plaid_client()
    db = _db()
    uid = str(user.get("uid") or "")
    uref = db.collection("users").document(uid)
    items = list(uref.collection("plaid_items").stream())
    if not items:
        return {"ok": True, "synced": 0}
    total_added = 0
    for d in items:
        rec = d.to_dict() or {}
        access_token = rec.get("access_token") or ""
        cursor = rec.get("cursor") or None
        if not access_token:
            continue
        accounts = client.accounts_get(AccountsGetRequest(access_token=access_token)).to_dict()
        acct_map = {}
        for a in accounts.get("accounts") or []:
            name = str(a.get("name") or a.get("official_name") or "Account")
            mask = str(a.get("mask") or "")
            acct_map[str(a.get("account_id") or "")] = f"{name} ****{mask}" if mask else name
        has_more = True
        added_count = 0
        new_cursor = cursor
        while has_more:
            resp = client.transactions_sync(TransactionsSyncRequest(access_token=access_token, cursor=new_cursor)).to_dict()
            new_cursor = resp.get("next_cursor") or new_cursor
            has_more = bool(resp.get("has_more"))
            added = resp.get("added") or []
            if added:
                batch = db.batch()
                tcol = uref.collection("transactions")
                upload_id = f"plaid:{d.id}:{new_cursor or 'init'}"
                for tx in added:
                    acc_id = str(tx.get("account_id") or "")
                    src = acct_map.get(acc_id) or "Plaid Account"
                    memo = str(tx.get("merchant_name") or tx.get("name") or "").strip()
                    amount = float(tx.get("amount") or 0.0)
                    date = _mmddyyyy(str(tx.get("date") or ""))
                    batch.set(
                        tcol.document(),
                        {
                            "date": date,
                            "dateKey": date.replace("/", ""),
                            "memo": memo,
                            "amount": amount,
                            "account": "",
                            "source": src,
                            "uploadId": upload_id,
                            "fileName": "Plaid",
                            "createdAt": fa_firestore.SERVER_TIMESTAMP,
                        },
                    )
                batch.commit()
                added_count += len(added)
        uref.collection("plaid_items").document(d.id).set({"cursor": new_cursor, "updatedAt": fa_firestore.SERVER_TIMESTAMP}, merge=True)
        if added_count:
            uref.collection("plaid_syncs").document().set(
                {"itemId": d.id, "institution": rec.get("institution") or "", "transactionCount": int(added_count), "createdAt": fa_firestore.SERVER_TIMESTAMP}
            )
            total_added += added_count
    return {"ok": True, "synced": int(total_added)}

@router.post("/webhook")
def webhook(payload: Dict[str, Any] = Body(...), authorization: str | None = Header(None)):
    return {"ok": True}
