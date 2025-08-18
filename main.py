from typing import Iterable
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os

# Your parser — keep as is in your repo
from universal_parser import extract_transactions_from_bytes

# Firebase / Firestore
import firebase_admin
from firebase_admin import auth as fb_auth
from google.cloud import firestore

# -------------------------- App & CORS -------------------------- #
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

# ---------------------- Firebase utilities --------------------- #
def _init_firebase_once():
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()

def _db():
    return firestore.Client()

def _verify_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1].strip()
    _init_firebase_once()
    try:
        decoded = fb_auth.verify_id_token(token, check_revoked=False)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    uid = decoded.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid token")
    return uid

# ---------------------- Small helpers -------------------------- #
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
    """
    Parse a PDF, write transactions with an uploadId, and write an upload
    metadata row that the Link+Load page reads (fileName/source/transactionCount).
    """
    uid = _verify_bearer(authorization)
    pdf_bytes = await file.read()

    # Parse
    rows, meta = extract_transactions_from_bytes(pdf_bytes)  # returns (list[dict], dict)
    source = str(meta.get("source_account") or meta.get("source") or "Unknown")

    db = _db()
    uref = db.collection("users").document(uid)

    # Create the upload document (so we have its ID up front)
    upref = uref.collection("uploads").document()
    upload_id = upref.id

    batch = db.batch()

    # Upload metadata
    batch.set(upref, {
        "fileName": file.filename,
        "source": source,
        "transactionCount": int(len(rows or [])),
        "status": "ready",
        "createdAt": firestore.SERVER_TIMESTAMP,
        "updatedAt": firestore.SERVER_TIMESTAMP,
    })

    # Transactions with uploadId
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
    uid = _verify_bearer(authorization)
    pdf_bytes = await file.read()

    rows, meta = extract_transactions_from_bytes(pdf_bytes)
    source = str(meta.get("source_account") or meta.get("source") or "Unknown")

    db = _db()
    uref = db.collection("users").document(uid)
    upref = uref.collection("uploads").document(uploadId)

    # Ensure the upload exists
    if not upref.get().exists:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Delete existing transactions for this uploadId
    _delete_query(
        uref.collection("transactions").where("uploadId", "==", uploadId)
    )

    # Write new transactions for same uploadId
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

    # Update upload metadata
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
    uid = _verify_bearer(authorization)
    db = _db()
    uref = db.collection("users").document(uid)

    # Delete all tx for this upload
    _delete_query(uref.collection("transactions").where("uploadId", "==", uploadId))

    # Delete the upload doc
    uref.collection("uploads").document(uploadId).delete()

    return {"ok": True, "deletedUploadId": uploadId}

# ---------------------- Delete all uploads --------------------- #
@app.post("/delete-all-uploads")
async def delete_all_uploads(authorization: str = Header(None)):
    uid = _verify_bearer(authorization)
    db = _db()
    uref = db.collection("users").document(uid)

    # Delete all transactions that have an uploadId
    _delete_query(uref.collection("transactions").where("uploadId", ">=", ""))

    # Delete all upload docs
    _delete_query(uref.collection("uploads").where("fileName", ">=", ""))

    return {"ok": True}
