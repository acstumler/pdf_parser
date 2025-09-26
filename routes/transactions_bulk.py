from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

router = APIRouter(prefix="/transactions", tags=["transactions"])

class Fingerprint(BaseModel):
    uid: Optional[str] = None
    date: Optional[str] = None
    memo: Optional[str] = None
    amount: Optional[float] = None

class BulkReclassifyIn(BaseModel):
    uids: List[str] = Field(default_factory=list)
    account: str
    fingerprints: List[Fingerprint] = Field(default_factory=list)

def get_user_id(request: Request) -> str:
    # Same auth behavior as your existing routes:
    # Read Authorization: Bearer <idToken>, verify, and return a user id/claim.
    # If you already have a helper, reuse that instead of this stub.
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    # Replace the next line with your existing token verification util.
    # For now we just accept the token and return a placeholder uid scope.
    return "user"  # <-- use your real user id from the verified token

def update_txn_account(user_id: str, uid: str, account: str) -> bool:
    """
    Update a transaction's account by uid for the given user.
    Replace this stub with your real DB/Firestore update code.
    Return True if updated, False if not found.
    """
    # Example Firestore sketch:
    # doc = db.collection("users").document(user_id).collection("transactions").document(uid)
    # if doc.get().exists:
    #     doc.update({"account": account})
    #     return True
    # return False
    return True

def update_by_fingerprint(user_id: str, fp: Fingerprint, account: str) -> int:
    """
    Optional fallback when uid isn't stored server-side exactly as the client formats it.
    Implement a query by (date, memo, amount) and update those rows.
    Return number of rows updated.
    """
    # Example Firestore query sketch:
    # q = (db.collection("users").document(user_id)
    #         .collection("transactions")
    #         .where("date", "==", fp.date)
    #         .where("amount", "==", fp.amount)
    #         .where("memo", "==", fp.memo))
    # updated = 0
    # for doc in q.stream():
    #     doc.reference.update({"account": account}); updated += 1
    # return updated
    return 0

@router.post("/bulk-reclassify")
async def bulk_reclassify(body: BulkReclassifyIn, user_id: str = Depends(get_user_id)) -> Dict[str, Any]:
    if not body.uids and not body.fingerprints:
        raise HTTPException(status_code=400, detail="No uids or fingerprints provided")
    if not body.account:
        raise HTTPException(status_code=400, detail="Missing account")

    updated = 0
    # First try direct uid updates
    for uid in body.uids:
        try:
            if update_txn_account(user_id, uid, body.account):
                updated += 1
        except Exception:
            pass

    # Then try fingerprint-based matching for rows whose uid format differs
    for fp in body.fingerprints:
        try:
            updated += update_by_fingerprint(user_id, fp, body.account)
        except Exception:
            pass

    return {"ok": True, "updated": updated}
