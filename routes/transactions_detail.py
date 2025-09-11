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

@router.get("/{tid}")
def get_one(tid: str, user: Dict[str, Any] = Depends(require_auth)):
    uid = str(user.get("uid") or "")
    db = _db()
    tcol = db.collection("users").document(uid).collection("transactions")
    for d in tcol.stream():
        t = d.to_dict() or {}
        if (t.get("id") or _uid_for(t)) == tid:
            return {"transaction": {**t, "id": tid}}
    raise HTTPException(status_code=404, detail="Transaction not found")

@router.post("/{tid}/reclassify")
def reclassify(tid: str, body: Dict[str, Any], user: Dict[str, Any] = Depends(require_auth)):
    uid = str(user.get("uid") or "")
    account = str((body or {}).get("account") or "")
    if not account:
        raise HTTPException(status_code=400, detail="Missing account")
    db = _db()
    tcol = db.collection("users").document(uid).collection("transactions")
    target_ref = None
    target_doc = None
    for d in tcol.stream():
        t = d.to_dict() or {}
        if (t.get("id") or _uid_for(t)) == tid:
            target_ref = d.reference
            target_doc = t
            break
    if target_ref is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    target_ref.update({"account": account})
    memo = str(target_doc.get("memo_clean") or target_doc.get("memo") or target_doc.get("memo_raw") or "").strip()
    if memo:
        vendor_key = clean_vendor_name(memo).lower()
        db.collection("users").document(uid).collection("vendor_memory").document(vendor_key).set(
            {"memoSample": memo, "account": account}, merge=True
        )
    return {"ok": True, "account": account}
