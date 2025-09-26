from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Dict, Any

router = APIRouter(prefix="/vendors", tags=["vendors"])

class PairIn(BaseModel):
    memo: str
    account: str

class TrainBulkIn(BaseModel):
    pairs: List[PairIn] = Field(default_factory=list)

def get_user_id(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return "user"  # replace with your real auth util

def upsert_vendor_mapping(user_id: str, memo: str, account: str) -> None:
    """
    Upsert vendor→account memory for this user (and optionally also a global map).
    Replace with your actual persistence logic.
    """
    # Example Firestore sketch:
    # key = memo.strip().lower()
    # db.collection("vendor_memory").document("global").set({key: account}, merge=True)
    # db.collection("users").document(user_id).collection("vendor_memory").document(key).set({"account": account})
    return

@router.post("/train-bulk")
async def train_bulk(body: TrainBulkIn, user_id: str = Depends(get_user_id)) -> Dict[str, Any]:
    if not body.pairs:
        raise HTTPException(status_code=400, detail="No pairs provided")
    for p in body.pairs:
        if not p.memo or not p.account:
            continue
        upsert_vendor_mapping(user_id, p.memo, p.account)
    return {"ok": True, "trained": len(body.pairs)}
