from typing import Dict, Any
from fastapi import APIRouter, Body, Depends, HTTPException, status
from .security import require_auth

router = APIRouter(prefix="/journal", tags=["journal"])

@router.post("/entries")
def entries(body: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_auth)):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
