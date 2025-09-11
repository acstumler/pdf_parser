from typing import Dict, Any
from fastapi import APIRouter, Body, Depends, HTTPException, status
from .security import require_auth
from firebase_admin import firestore as fa_firestore
from utils.clean_vendor_name import clean_vendor_name

router = APIRouter(prefix="/vendors", tags=["vendors"])

@router.post("/train")
def train(body: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_auth)):
    memo = str(body.get("memo") or "")
    account = str(body.get("account") or "")
    if not memo or not account:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    uid = str(user.get("uid") or "")
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    vendor_key = clean_vendor_name(memo).lower()
    if not vendor_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    db = fa_firestore.client()
    ref = db.collection("users").document(uid).collection("vendor_memory").document(vendor_key)
    ref.set(
        {"account": account, "vendorKey": vendor_key, "memoSample": memo, "updatedAt": fa_firestore.SERVER_TIMESTAMP},
        merge=True,
    )
    return {"ok": True, "vendorKey": vendor_key, "account": account}
