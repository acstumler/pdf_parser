from typing import Dict, Any, List
from fastapi import APIRouter, Body, Depends, HTTPException, status
from .security import require_auth

router = APIRouter(prefix="/journal", tags=["journal"])

def _to_number(x: Any) -> float:
    if isinstance(x, (int, float)):
        return float(x)
    s = (str(x) if x is not None else "")
    out = []
    for ch in s:
        if (ch >= "0" and ch <= "9") or ch in ".-":
            out.append(ch)
    try:
        return float("".join(out)) if out else 0.0
    except Exception:
        return 0.0

def _uid_for(t: Dict[str, Any]) -> str:
    date = (t.get("date") or "").split("T")[0] or (t.get("date") or "")
    memo = str(t.get("memo_clean") or t.get("memo") or t.get("memo_raw") or "")[:24]
    try:
        amount = float(t.get("amount") or 0.0)
    except Exception:
        amount = 0.0
    return f"{date}-{memo}-{amount}"

@router.post("/entries")
def entries(body: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_auth)):
    txns: List[Dict[str, Any]] = body.get("transactions") or []
    if not isinstance(txns, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    lines: List[Dict[str, Any]] = []
    for i, t in enumerate(txns):
        date = str(t.get("date") or "")
        memo = str(t.get("memo_clean") or t.get("memo") or t.get("memo_raw") or "")
        amount = _to_number(t.get("amount"))
        account = str(t.get("account") or "Uncategorized")
        source = str(t.get("source") or t.get("source_account") or "Offset")
        uploaded_at = t.get("uploadedAt")
        uploaded_from = t.get("uploadedFrom")

        abs_amt = abs(amount)
        txn_id = str(t.get("id") or _uid_for(t))

        debit_line = {
            "id": f"{i}-debit",
            "txnId": txn_id,
            "date": date,
            "memo": memo,
            "account": account if amount >= 0 else source,
            "type": "Debit",
            "amount": abs_amt,
            "uploadedAt": uploaded_at,
            "uploadedFrom": uploaded_from,
        }
        credit_line = {
            "id": f"{i}-credit",
            "txnId": txn_id,
            "date": date,
            "memo": memo,
            "account": account if amount < 0 else source,
            "type": "Credit",
            "amount": abs_amt,
            "uploadedAt": uploaded_at,
            "uploadedFrom": uploaded_from,
        }
        lines.append(debit_line)
        lines.append(credit_line)

    return {"ok": True, "entries": lines}
