from typing import Any, Optional
from datetime import datetime, timedelta
from google.cloud import firestore

def _absf(x: Any) -> float:
    try:
        return abs(float(x or 0.0))
    except Exception:
        return 0.0

def _to_datekey(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y%m%d")
        except Exception:
            pass
    return ""

def _from_datekey(k: str) -> Optional[datetime]:
    try:
        return datetime.strptime(k, "%Y%m%d")
    except Exception:
        return None

def _range_keys(center_key: str, days: int = 5) -> tuple[str, str]:
    dt = _from_datekey(center_key) or datetime.utcnow()
    a = (dt - timedelta(days=days)).strftime("%Y%m%d")
    b = (dt + timedelta(days=days)).strftime("%Y%m%d")
    return a, b

def _has_bank_match(db: firestore.Client, uid: str, date_key: str, amount_abs: float, tol: float = 0.01) -> bool:
    if not date_key or amount_abs <= 0:
        return False
    start, end = _range_keys(date_key, days=5)
    uref = db.collection("users").document(uid)
    q = (
        uref.collection("transactions")
        .where("dateKey", ">=", start)
        .where("dateKey", "<=", end)
        .where("sourceType", "==", "bank")
    )
    try:
        for d in q.stream():
            rec = d.to_dict() or {}
            a = _absf(rec.get("amount"))
            if abs(a - amount_abs) <= tol:
                return True
    except Exception:
        pass
    return False

def compute_display_amount(
    *,
    db: Optional[firestore.Client],
    uid: Optional[str],
    amount: float,
    source_type: str,
    date: str = "",
    date_key: str = ""
) -> float:
    st = (source_type or "").strip().lower()
    try:
        amt = float(amount or 0.0)
    except Exception:
        amt = 0.0
    key = date_key or _to_datekey(date)
    if st == "bank":
        return _absf(amt) if amt >= 0 else -_absf(amt)
    if st == "card":
        if amt > 0:
            return _absf(amt)
        is_payment = False
        if db is not None and uid:
            try:
                is_payment = _has_bank_match(db, uid, key, _absf(amt))
            except Exception:
                is_payment = False
        return _absf(amt) if is_payment else -_absf(amt)
    return amt
