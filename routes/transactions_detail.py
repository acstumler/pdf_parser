from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict
from firebase_admin import firestore as fa_firestore
from .security import require_auth
from utils.clean_vendor_name import clean_vendor_name

router = APIRouter(prefix="/transactions", tags=["transactions"])

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

def _find_transaction_doc(db, uid: str, tid: str):
    tcol = db.collection("users").document(uid).collection("transactions")
    snap = tcol.document(tid).get()
    if snap.exists:
        return snap.reference, (snap.to_dict() or {})
    for d in tcol.stream():
        t = d.to_dict() or {}
        if _uid_for(t) == tid:
            return d.reference, t
    return None, None

@router.get("/{tid}")
def get_one(tid: str, user: Dict[str, Any] = Depends(require_auth)):
    uid = str(user.get("uid") or "")
    db = _db()
    ref, doc = _find_transaction_doc(db, uid, tid)
    if not ref:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"transaction": {**doc, "id": tid}}

@router.post("/{tid}/reclassify")
def reclassify(tid: str, body: Dict[str, Any], user: Dict[str, Any] = Depends(require_auth)):
    uid = str(user.get("uid") or "")
    account = str((body or {}).get("account") or "")
    if not account:
        raise HTTPException(status_code=400, detail="Missing account")
    db = _db()
    ref, doc = _find_transaction_doc(db, uid, tid)
    if not ref:
        raise HTTPException(status_code=404, detail="Transaction not found")
    ref.update({"account": account})
    memo = str(doc.get("memo_clean") or doc.get("memo") or doc.get("memo_raw") or "").strip()
    if memo:
        vendor_key = clean_vendor_name(memo).lower()
        db.collection("users").document(uid).collection("vendor_memory").document(vendor_key).set(
            {"memoSample": memo, "account": account}, merge=True
        )
    return {"ok": True, "account": account}
