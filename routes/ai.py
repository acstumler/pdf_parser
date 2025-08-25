from typing import Dict, Any
from fastapi import APIRouter, Body, Depends, HTTPException, status
from .security import require_auth

router = APIRouter(prefix="/ai", tags=["ai"])

@router.post("/embedding")
def embedding(payload: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_auth)):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
