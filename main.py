from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Response, Header, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from universal_parser import extract_transactions_from_bytes
from google.cloud import firestore
import firebase_admin
from firebase_admin import auth as fb_auth
from datetime import datetime
import os
from classify_transaction import classify_llm

app = FastAPI(title="LumiLedger Parser API")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*vercel\.app$",
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

def _init_firebase_once():
  try:
    firebase_admin.get_app()
  except ValueError:
    firebase_admin.initialize_app()

def _firestore_client():
  return firestore.Client()

def _verify_bearer(authorization: str | None) -> str:
  if not authorization or not authorization.lower().startswith("bearer "):
    raise HTTPException(status_code=401, detail="Missing token")
  token = authorization.split(" ", 1)[1].strip()
  _init_firebase_once()
  decoded = fb_auth.verify_id_token(token, check_revoked=False)
  uid = decoded.get("uid", "")
  if not uid:
    raise HTTPException(status_code=401, detail="Invalid token")
  return uid

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

def _collapse_spaces(s: str) -> str:
  if not s:
    return ""
  out = []
  prev_space = False
  for ch in s:
    space = ch in (" ", "\t", "\n", "\r")
    if space:
      if not prev_space:
        out.append(" ")
      prev_space = True
    else:
      out.append(ch)
      prev_space = False
  return "".join(out).strip()

def _canonicalize_vendor(memo: str) -> str:
  s = _collapse_spaces((memo or "").lower())
  out = []
  for ch in s:
    if "a" <= ch <= "z" or ch == " ":
      out.append(ch)
  key = "".join(out).strip()
  return key[:64]

@app.get("/health")
def health():
  return {"ok": True}

@app.post("/parse-and-persist")
async def parse_and_persist(authorization: str = Header(None), file: UploadFile = File(...)):
  uid = _verify_bearer(authorization)
  pdf_bytes = await file.read()
  rows, meta = extract_transactions_from_bytes(pdf_bytes)
  db = _firestore_client()
  batch = db.batch()
  uref = db.collection("users").document(uid)
  upref = uref.collection("uploads").document()
  batch.set(upref, {"filename": file.filename, "createdAt": firestore.SERVER_TIMESTAMP})
  tref = uref.collection("transactions")
  for r in rows:
    memo = str(r.get("memo") or r.get("memo_raw") or r.get("memo_clean") or "")
    date = str(r.get("date") or "")
    amount = float(r.get("amount") or 0)
    source = str(meta.get("source_account") or r.get("source") or "")
    dateKey = _parse_date_key(date)
    doc = tref.document()
    batch.set(doc, {
      "date": date,
      "dateKey": dateKey,
      "memo": memo,
      "amount": amount,
      "source": source,
      "account": r.get("account") or ""
    })
  batch.commit()
  return {"ok": True, "count": len(rows)}

@app.get("/transactions")
def list_transactions(authorization: str = Header(None)):
  uid = _verify_bearer(authorization)
  db = _firestore_client()
  q = db.collection("users").document(uid).collection("transactions").order_by("dateKey")
  rows = []
  for doc in q.stream():
    d = doc.to_dict() or {}
    d["id"] = doc.id
    rows.append(d)
  return {"transactions": rows}

@app.get("/uploads")
def list_uploads(authorization: str = Header(None)):
  uid = _verify_bearer(authorization)
  db = _firestore_client()
  q = db.collection("users").document(uid).collection("uploads").order_by("createdAt", direction=firestore.Query.DESCENDING)
  rows = []
  for doc in q.stream():
    d = doc.to_dict() or {}
    d["id"] = doc.id
    rows.append(d)
  return {"uploads": rows}

@app.post("/classify-batch")
def classify_batch(authorization: str = Header(None), payload: Dict[str, Any] = Body(...)):
  uid = _verify_bearer(authorization)
  items: List[Dict[str, Any]] = payload.get("items") or []
  allowed_accounts = payload.get("allowedAccounts") or None
  db = _firestore_client()
  out = []
  for it in items:
    _id = str(it.get("id", ""))
    memo = str(it.get("memo", ""))
    amount = float(it.get("amount", 0) or 0)
    source = str(it.get("source", ""))
    vendor_key = _canonicalize_vendor(memo)
    mem_ref = db.collection("users").document(uid).collection("vendorMemory").document(vendor_key)
    mem_snap = mem_ref.get()
    if mem_snap.exists:
      acc = (mem_snap.to_dict() or {}).get("account", "")
      out.append({"id": _id, "account": acc or "", "via": "memory"})
      continue
    account = classify_llm(memo=memo, amount=amount, source=source, allowed_accounts=allowed_accounts)
    out.append({"id": _id, "account": account or "", "via": "ai"})
  return {"items": out}

@app.post("/train-vendor")
def train_vendor(authorization: str = Header(None), payload: Dict[str, Any] = Body(...)):
  uid = _verify_bearer(authorization)
  vendor_key = _canonicalize_vendor(str(payload.get("vendorKey", "")))
  account = str(payload.get("account", "")).strip()
  if not vendor_key or not account:
    raise HTTPException(status_code=400, detail="vendorKey and account required")
  db = _firestore_client()
  ref = db.collection("users").document(uid).collection("vendorMemory").document(vendor_key)
  ref.set({"account": account, "updatedAt": firestore.SERVER_TIMESTAMP, "learnedFrom": "manual"}, merge=True)
  return {"ok": True}
