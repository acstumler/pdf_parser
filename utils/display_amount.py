from typing import Any, Optional, Dict
from datetime import datetime, timedelta
from google.cloud import firestore

def _absf(x: Any) -> float:
    try:
        return abs(float(x or 0.0))
    except Exception:
        return 0.0

def _sign(x: Any) -> int:
    try:
        v = float(x or 0.0)
    except Exception:
        v = 0.0
    return 1 if v > 0 else (-1 if v < 0 else 0)

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
    # detect a payment to the card by finding a bank txn with the same absolute amount near the same date
    if not date_key or amount_abs <= 0:
        return False
    start, end = _range_keys(date_key, days=5)
    uref = db.collection("users").document(uid)
    q = (uref.collection("transactions")
         .where("dateKey", ">=", start)
         .where("dateKey", "<=", end)
         .where("sourceType", "==", "bank"))
    try:
        for d in q.stream():
            rec = d.to_dict() or {}
            a = _absf(rec.get("amount"))
            if abs(a - amount_abs) <= tol:
                return True
    except Exception:
        pass
    return False

def _source_key(s: str) -> str:
    return (s or "").strip().lower()

def _get_policy(db: firestore.Client, uid: str, source: str, source_type: str) -> Dict[str, int]:
    """
    Returns a policy dict like:
      bank: {"outflow_sign": +1 or -1}
      card: {"charge_sign": +1 or -1}
    Chooses the majority sign in recent history for this source; writes it to Firestore for reuse.
    """
    uref = db.collection("users").document(uid)
    pref = uref.collection("source_policies").document(_source_key(source))
    snap = pref.get()
    if snap.exists:
        data = snap.to_dict() or {}
        if source_type == "bank" and "outflow_sign" in data:
            return {"outflow_sign": int(data["outflow_sign"])}
        if source_type == "card" and "charge_sign" in data:
            return {"charge_sign": int(data["charge_sign"])}

    # derive from recent txns
    pos = 0
    neg = 0
    try:
      q = (uref.collection("transactions")
           .where("source", "==", source)
           .order_by("createdAt", direction=firestore.Query.DESCENDING)  # type: ignore
           .limit(150))
      for d in q.stream():
          amt = float((d.to_dict() or {}).get("amount") or 0.0)
          sgn = _sign(amt)
          if sgn > 0: pos += 1
          elif sgn < 0: neg += 1
    except Exception:
      pass

    if source_type == "bank":
        outflow_sign = 1 if pos >= neg else -1
        pref.set({"sourceType": "bank", "outflow_sign": outflow_sign}, merge=True)
        return {"outflow_sign": outflow_sign}

    # card
    charge_sign = 1 if pos >= neg else -1
    pref.set({"sourceType": "card", "charge_sign": charge_sign}, merge=True)
    return {"charge_sign": charge_sign}

def compute_display_amount(
    *,
    db: Optional[firestore.Client],
    uid: Optional[str],
    amount: float,
    source_type: str,
    source: str,
    date: str = "",
    date_key: str = ""
) -> float:
    """
    Universal accountant-view:
      Bank (asset): outflow -> + ; inflow -> -
      Card (liability): charge -> + ; refund/credit -> - ; payment (to card) -> +
    Uses per-source sign policy so mixed Plaid conventions normalize correctly.
    """
    st = (source_type or "").strip().lower()
    key = date_key or _to_datekey(date)
    sgn = _sign(amount)
    abs_amt = _absf(amount)

    if not db or not uid:
        # Fallback to original heuristic if no DB context
        if st == "bank":
            return abs_amt if sgn >= 0 else -abs_amt
        if st == "card":
            return abs_amt if sgn > 0 else -abs_amt
        return amount

    policy = _get_policy(db, uid, source, st)

    if st == "bank":
        outflow_sign = int(policy.get("outflow_sign", 1))
        outflow = (sgn == outflow_sign) or (sgn == 0 and outflow_sign == 1)
        return abs_amt if outflow else -abs_amt

    if st == "card":
        charge_sign = int(policy.get("charge_sign", 1))
        if sgn == charge_sign or (sgn == 0 and charge_sign == 1):
            return abs_amt  # charge
        # inflow to card -> refund or payment
        is_payment = _has_bank_match(db, uid, key, abs_amt)
        return abs_amt if is_payment else -abs_amt

    return amount
