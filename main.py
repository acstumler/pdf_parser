from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Response, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from universal_parser import extract_transactions_from_bytes
from google.cloud import firestore
import firebase_admin
from firebase_admin import auth as fb_auth, credentials as fb_credentials
from datetime import datetime

app = FastAPI(title="LumiLedger Parser API")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*vercel\.app$",
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.router.redirect_slashes = False

def _init_firebase_once():
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()

def _firestore_client():
    return firestore.Client()

def _parse_date_key(s: str) -> str:
    if not s:
        return ""
    try:
        dt = datetime.strptime(s, "%m/%d/%Y")
        return dt.strftime("%Y%m%d")
    except Exception:
        try:
            dt = datetime.fromisoformat(s)
            return dt.strftime("%Y%m%d")
        except Exception:
            return ""

@app.get("/health")
def health():
    return {"ok": True}

@app.options("/parse-universal")
@app.options("/parse-universal/")
@app.options("/parse-and-persist")
@app.options("/replace-upload")
@app.options("/delete-upload")
def _preflight_ok():
    return Response(status_code=204)

def _normalize_rows(rows: List[Dict[str, Any]], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    meta = meta or {}
    source = str(meta.get("source_account", ""))
    out: List[Dict[str, Any]] = []
    for r in rows or []:
        date = str(r.get("date", ""))
        memo_clean = str(r.get("memo_clean", "") or r.get("memo", ""))
        amount_val = r.get("amount", 0)
        try:
            amount = float(amount_val if amount_val not in [None, ""] else 0)
        except Exception:
            amount = 0.0
        src = str(r.get("source", "") or r.get("source_account", "") or source)
        out.append(
            {
                "date": date,
                "dateKey": _parse_date_key(date),
                "memo_raw": str(r.get("memo_raw", "")),
                "memo_clean": memo_clean,
                "amount": amount,
                "source": src,
                "source_account": str(r.get("source_account", "") or source),
                "account": r.get("account", ""),
                "account_sub": r.get("account_sub", ""),
                "account_main": r.get("account_main", ""),
            }
        )
    return out

@app.post("/parse-universal")
@app.post("/parse-universal/")
async def parse_universal(file: UploadFile = File(...)):
    try:
        pdf_bytes = await file.read()
        rows, meta = extract_transactions_from_bytes(pdf_bytes)
        txns = _normalize_rows(rows if isinstance(rows, list) else [], meta or {})
        return JSONResponse(
            {
                "transactions": txns,
                "source": str((meta or {}).get("source_account", "")),
                "source_account": str((meta or {}).get("source_account", "")),
                "statement_end_date": str((meta or {}).get("statement_end_date", "")),
                "errors": [],
            }
        )
    except Exception as e:
        return JSONResponse(
            {
                "transactions": [],
                "source": "",
                "source_account": "",
                "statement_end_date": "",
                "errors": [str(e)],
            },
            status_code=200,
        )

def _verify_bearer(token_header: str) -> str:
    if not token_header or not token_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = token_header.split(" ", 1)[1].strip()
    try:
        _init_firebase_once()
        decoded = fb_auth.verify_id_token(token)
        uid = decoded.get("uid")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")
        return uid
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

def _write_upload_and_transactions(db: firestore.Client, uid: str, upload_id: str, upload_doc: Dict[str, Any], txns: List[Dict[str, Any]]):
    upload_ref = db.collection("users").document(uid).collection("uploads").document(upload_id)
    batch = db.batch()
    batch.set(upload_ref, upload_doc)
    batch.commit()
    chunk_size = 400
    tx_ref = db.collection("users").document(uid).collection("transactions")
    for i in range(0, len(txns), chunk_size):
        batch = db.batch()
        for t in txns[i:i+chunk_size]:
            doc_ref = tx_ref.document()
            batch.set(doc_ref, {**t, "uploadId": upload_id, "createdAt": firestore.SERVER_TIMESTAMP})
        batch.commit()

@app.post("/parse-and-persist")
async def parse_and_persist(authorization: str = Header(None), file: UploadFile = File(...)):
    uid = _verify_bearer(authorization)
    try:
        pdf_bytes = await file.read()
        rows, meta = extract_transactions_from_bytes(pdf_bytes)
        txns = _normalize_rows(rows if isinstance(rows, list) else [], meta or {})
        upload_id = f"{file.filename}-{int(datetime.utcnow().timestamp()*1000)}"
        source_label = str((meta or {}).get("source_account", "")) or (txns[0]["source"] if txns else "")
        upload_doc = {
            "fileName": file.filename,
            "source": source_label,
            "transactionCount": len(txns),
            "createdAt": firestore.SERVER_TIMESTAMP,
            "status": "parsed",
        }
        db = _firestore_client()
        _write_upload_and_transactions(db, uid, upload_id, upload_doc, txns)
        return {"uploadId": upload_id, "transactionCount": len(txns), "source": source_label}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/replace-upload")
async def replace_upload(authorization: str = Header(None), uploadId: str = "", file: UploadFile = File(...)):
    uid = _verify_bearer(authorization)
    if not uploadId:
        raise HTTPException(status_code=400, detail="uploadId required")
    try:
        pdf_bytes = await file.read()
        rows, meta = extract_transactions_from_bytes(pdf_bytes)
        txns = _normalize_rows(rows if isinstance(rows, list) else [], meta or {})
        db = _firestore_client()
        tx_ref = db.collection("users").document(uid).collection("transactions")
        to_delete = tx_ref.where("uploadId", "==", uploadId).stream()
        del_batch = db.batch()
        count = 0
        for doc in to_delete:
            del_batch.delete(doc.reference)
            count += 1
            if count % 400 == 0:
                del_batch.commit()
                del_batch = db.batch()
        del_batch.commit()
        source_label = str((meta or {}).get("source_account", "")) or (txns[0]["source"] if txns else "")
        upload_ref = db.collection("users").document(uid).collection("uploads").document(uploadId)
        upload_ref.set({
            "fileName": file.filename,
            "source": source_label,
            "transactionCount": len(txns),
            "createdAt": firestore.SERVER_TIMESTAMP,
            "status": "parsed",
        }, merge=True)
        _write_upload_and_transactions(db, uid, uploadId, {}, txns)
        return {"uploadId": uploadId, "transactionCount": len(txns), "source": source_label}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/delete-upload")
async def delete_upload(authorization: str = Header(None), uploadId: str = ""):
    uid = _verify_bearer(authorization)
    if not uploadId:
        raise HTTPException(status_code=400, detail="uploadId required")
    try:
        db = _firestore_client()
        tx_ref = db.collection("users").document(uid).collection("transactions")
        to_delete = tx_ref.where("uploadId", "==", uploadId).stream()
        del_batch = db.batch()
        count = 0
        for doc in to_delete:
            del_batch.delete(doc.reference)
            count += 1
            if count % 400 == 0:
                del_batch.commit()
                del_batch = db.batch()
        del_batch.commit()
        db.collection("users").document(uid).collection("uploads").document(uploadId).delete()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
