from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime, timedelta
from google.cloud import firestore

WINDOW_DAYS = 5
AMOUNT_TOL = 0.01

def _absf(x: Any) -> float:
    try:
        return abs(float(x or 0.0))
    except Exception:
        return 0.0

def _datekey(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if len(s) == 8 and s.isdigit():
        return s
    try:
        return datetime.strptime(s, "%m/%d/%Y").strftime("%Y%m%d")
    except Exception:
        pass
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%Y%m%d")
    except Exception:
        return ""

def _range_keys(center_key: str, days: int) -> Tuple[str, str]:
    try:
        dt = datetime.strptime(center_key, "%Y%m%d")
    except Exception:
        dt = datetime.utcnow()
    a = (dt - timedelta(days=days)).strftime("%Y%m%d")
    b = (dt + timedelta(days=days)).strftime("%Y%m%d")
    return a, b

def _find_candidate(db: firestore.Client, uid: str, *, want_inflow: bool, amount_abs: float, start_key: str, end_key: str, types: List[str], exclude_doc_id: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    uref = db.collection("users").document(uid)
    q = (uref.collection("transactions")
         .where("dateKey", ">=", start_key)
         .where("dateKey", "<=", end_key)
         .where("sourceType", "in", types))
    try:
        for d in q.stream():
            if d.id == exclude_doc_id:
                continue
            rec = d.to_dict() or {}
            amt = float(rec.get("amount") or 0.0)
            if want_inflow and amt >= 0:
                continue
            if (not want_inflow) and amt <= 0:
                continue
            if abs(_absf(amt) - amount_abs) <= AMOUNT_TOL:
                return d.id, rec
    except Exception:
        return None
    return None

def pair_on_ingest(db: firestore.Client, uid: str, doc_id: str) -> Optional[str]:
    dref = db.collection("users").document(uid).collection("transactions").document(doc_id)
    snap = dref.get()
    if not snap.exists:
        return None
    row = snap.to_dict() or {}
    if row.get("pairId"):
        return row.get("pairId")

    st = str(row.get("sourceType") or "").lower()
    amt = float(row.get("amount") or 0.0)
    dk = _datekey(row.get("date") or row.get("dateKey") or "")
    if not dk:
        return None

    start_key, end_key = _range_keys(dk, WINDOW_DAYS)
    amount_abs = _absf(amt)

    if st == "bank" and amt >= 0:
        found = _find_candidate(db, uid, want_inflow=True, amount_abs=amount_abs, start_key=start_key, end_key=end_key, types=["card", "loan"], exclude_doc_id=doc_id)
        if found:
            other_id, other = found
            pair_id = f"pair:{min(doc_id, other_id)}:{max(doc_id, other_id)}"
            dref.set({"pairId": pair_id, "eventLeader": True, "pairedWith": other_id, "pairReason": "card_payment" if (other.get("sourceType") == "card") else "loan_payment"}, merge=True)
            db.collection("users").document(uid).collection("transactions").document(other_id).set({"pairId": pair_id, "eventLeader": False, "pairedWith": doc_id, "pairReason": "shadow"}, merge=True)
            return pair_id

    if st == "bank" and amt < 0:
        found = _find_candidate(db, uid, want_inflow=False, amount_abs=amount_abs, start_key=start_key, end_key=end_key, types=["bank"], exclude_doc_id=doc_id)
        if found:
            other_id, other = found
            pair_id = f"pair:{min(doc_id, other_id)}:{max(doc_id, other_id)}"
            leader = other_id if float(other.get("amount") or 0.0) >= 0 else doc_id
            shadow = doc_id if leader == other_id else other_id
            db.collection("users").document(uid).collection("transactions").document(leader).set({"pairId": pair_id, "eventLeader": True, "pairedWith": shadow, "pairReason": "bank_transfer"}, merge=True)
            db.collection("users").document(uid).collection("transactions").document(shadow).set({"pairId": pair_id, "eventLeader": False, "pairedWith": leader, "pairReason": "shadow"}, merge=True)
            return pair_id

    if st in ("card", "loan") and amt <= 0:
        found = _find_candidate(db, uid, want_inflow=False, amount_abs=amount_abs, start_key=start_key, end_key=end_key, types=["bank"], exclude_doc_id=doc_id)
        if found:
            other_id, _ = found
            pair_id = f"pair:{min(doc_id, other_id)}:{max(doc_id, other_id)}"
            db.collection("users").document(uid).collection("transactions").document(other_id).set({"pairId": pair_id, "eventLeader": True, "pairedWith": doc_id, "pairReason": "card_payment" if st == "card" else "loan_payment"}, merge=True)
            dref.set({"pairId": pair_id, "eventLeader": False, "pairedWith": other_id, "pairReason": "shadow"}, merge=True)
            return pair_id

    return None
