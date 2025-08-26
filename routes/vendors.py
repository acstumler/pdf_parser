from typing import Dict, Any
from fastapi import APIRouter, Body, Depends, HTTPException, status
from .security import require_auth
import firebase_admin
from firebase_admin import firestore as fa_firestore

router = APIRouter(prefix="/vendors", tags=["vendors"])

def _collapse_spaces(s: str) -> str:
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

def _canonical_vendor(memo: str) -> str:
    base = _collapse_spaces((memo or "").lower())
    out = []
    for ch in base:
        if (ch >= "a" and ch <= "z") or ch == " ":
            out.append(ch)
    key = "".join(out).strip()
    if len(key) > 64:
        key = key[:64]
    return key

@router.post("/train")
def train(body: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_auth)):
    memo = str(body.get("memo") or "")
    account = str(body.get("account") or "")
    if not memo or not account:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    uid = str(user.get("uid") or "")
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    vendor_key = _canonical_vendor(memo)
    if not vendor_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    db = fa_firestore.client()
    ref = db.collection("users").document(uid).collection("vendor_memory").document(vendor_key)
    ref.set(
        {"account": account, "vendorKey": vendor_key, "memoSample": memo, "updatedAt": fa_firestore.SERVER_TIMESTAMP},
        merge=True,
    )
    return {"ok": True, "vendorKey": vendor_key, "account": account}
