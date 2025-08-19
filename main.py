from typing import Iterable
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import os

from universal_parser import extract_transactions_from_bytes

import firebase_admin
from firebase_admin import auth as fb_auth
from google.cloud import firestore

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
    # Enforce that the user's auth_time is recent (user just reauthenticated)
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

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/parse-and-persist")
async def parse_and_persist(authorization: str = Header(None), file: UploadFile = File(...)):
    decoded = _verify_and_decode(authorization)
    uid = decoded["uid"]
    pdf_bytes = await file.read()

    rows, meta = extract_transactions_from_bytes(pdf_bytes)
    source = str(meta.get("source_account") or meta.get("source") or "Unknown")

    db = _db()
    uref = db.collection("users").document(uid)
    upref = uref.collection("uploads").document()   # get generated id
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

@app.post("/delete-upload")
async def delete_upload(authorization: str = Header(None), uploadId: str = Query(..., min_length=1)):
    decoded = _verify_and_decode(authorization)
    uid = decoded["uid"]
    db = _db()
    uref = db.collection("users").document(uid)

    _delete_query(uref.collection("transactions").where("uploadId", "==", uploadId))
    uref.collection("uploads").document(uploadId).delete()

    return {"ok": True, "deletedUploadId": uploadId}

@app.post("/delete-all-uploads")
async def delete_all_uploads(authorization: str = Header(None)):
    decoded = _verify_and_decode(authorization)
    # Require a RECENT login (client reauths then calls this)
    _require_recent_login(decoded, max_age_sec=180)

    uid = decoded["uid"]
    db = _db()
    uref = db.collection("users").document(uid)

    _delete_query(uref.collection("transactions").where("uploadId", ">=", ""))
    _delete_query(uref.collection("uploads").where("fileName", ">=", ""))

    return {"ok": True}

@app.get("/transactions")
def list_transactions(
    authorization: str = Header(None),
    limit: int = Query(1000, ge=1, le=5000),
):
    decoded = _verify_and_decode(authorization)
    uid = decoded["uid"]
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
def list_uploads(
    authorization: str = Header(None),
    limit: int = Query(500, ge=1, le=2000),
):
    decoded = _verify_and_decode(authorization)
    uid = decoded["uid"]
    db = _db()
    uref = db.collection("users").document(uid)
    q = uref.collection("uploads").order_by("createdAt", direction=firestore.Query.DESCENDING).limit(limit)
    out = []
    for d in q.stream():
        doc = d.to_dict() or {}
        doc["id"] = d.id
        out.append(doc)
    return {"ok": True, "uploads": out}
