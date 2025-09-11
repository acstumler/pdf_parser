from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict
from firebase_admin import firestore as fa_firestore
from .security import require_auth

router = APIRouter(prefix="/journal", tags=["journal"])

def _db():
  return fa_firestore.client()

def _uid_for(t: Dict[str, Any]) -> str:
  date = (t.get("date") or "").split("T")[0] or (t.get("date") or "")
  memo = str(t.get("memo_clean") or t.get("memo") or t.get("memo_raw") or "")[:24]
  try:
    amount = float(t.get("amount") or 0.0)
  except Exception:
    amount = 0.0
  return f"{date}-{memo}-{amount}"

def _account_type(account: str) -> str:
  s = (account or "").strip()
  code = ""
  for ch in s:
    if ch.isdigit(): code += ch
    else: break
  if code:
    d = code[0]
    if d == "1": return "Asset"
    if d == "2": return "Liability"
    if d == "3": return "Equity"
    if d == "4": return "Income"
    if d == "5": return "COGS"
    if d in ("6","7","8","9"): return "Expense"
  if any(ch.isdigit() for ch in s[-6:]):
    return "Liability"
  return "Expense"

def _find_transaction_doc(db, uid: str, tid: str):
  tcol = db.collection("users").document(uid).collection("transactions")
  snap = tcol.document(tid).get()
  if snap.exists:
    return snap.to_dict() or {}
  for d in tcol.stream():
    t = d.to_dict() or {}
    if _uid_for(t) == tid:
      return t
  return None

@router.get("/entries/by-uid/{tid}")
def by_uid(tid: str, user: Dict[str, Any] = Depends(require_auth)):
  uid = str(user.get("uid") or "")
  db = _db()
  tdoc = _find_transaction_doc(db, uid, tid)
  if not tdoc:
    raise HTTPException(status_code=404, detail="Transaction not found")

  date = tdoc.get("date") or ""
  memo = str(tdoc.get("memo_clean") or tdoc.get("memo") or tdoc.get("memo_raw") or "")
  account = str(tdoc.get("account") or "")
  source = str(tdoc.get("source") or tdoc.get("source_account") or "Unknown Source")
  try:
    amount = abs(float(tdoc.get("amount") or 0))
  except Exception:
    amount = 0.0

  primary_is_debit = _account_type(account) in ("Expense", "COGS", "Asset")
  first = {"id": f"{tid}-1", "date": date, "account": account, "type": "Debit" if primary_is_debit else "Credit", "amount": amount, "memo": memo}
  second = {"id": f"{tid}-2", "date": date, "account": source, "type": "Credit" if primary_is_debit else "Debit", "amount": amount, "memo": memo}
  return {"entries": [first, second]}
