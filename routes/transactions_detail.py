from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict, Optional
from firebase_admin import firestore as fa_firestore
from .security import require_auth
from utils.clean_vendor_name import clean_vendor_name
import urllib.parse

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

def _date_key(s: str) -> str:
    s = (s or "").strip()
    if len(s) >= 10 and s[2:3] == "/" and s[5:6] == "/":
        return s[:10].replace("/", "")
    return ""

def _parse_amount_fragment(s: str) -> float:
    neg = "(" in s and ")" in s
    digits = []
    for ch in s:
        if (ch >= "0" and ch <= "9") or ch == "." or ch == "-":
            digits.append(ch)
    txt = "".join(digits) or "0"
    try:
        val = float(txt)
    except Exception:
        val = 0.0
    if neg and val > 0:
        val = -val
    return val

def _find_by_slug(db: fa_firestore.Client, uid: str, slug: str) -> Optional[Dict[str, Any]]:
    s = urllib.parse.unquote(slug or "")
    dk = _date_key(s)
    if not dk:
        return None
    # amount is at the end of the slug
    tail = s[-32:]
    amt = _parse_amount_fragment(tail)
    tgt = abs(amt)
    uref = db.collection("users").document(uid)
    q = uref.collection("transactions").where("dateKey", "==", dk)
    try:
        for d in q.stream():
            rec = d.to_dict() or {}
            a = abs(float(rec.get("amount") or 0.0))
            if abs(a - tgt) <= 0.01:
                rec["__id"] = d.id
                return rec
    except Exception:
        return None
    return None

def _find_transaction_doc(db: fa_firestore.Client, uid: str, tid: str):
    tcol = db.collection("users").document(uid).collection("transactions")
    # 1) doc id
    snap = tcol.document(tid).get()
    if snap.exists:
        return snap.reference, (snap.to_dict() or {})
    # 2) derived uid
    for d in tcol.stream():
        t = d.to_dict() or {}
        if (t.get("id") or _uid_for(t)) == tid:
            return d.reference, t
    # 3) slug fallback
    rec = _find_by_slug(db, uid, tid)
    if rec:
        return tcol.document(rec["__id"]), rec
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
