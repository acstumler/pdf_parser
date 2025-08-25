from typing import Dict, Any
from fastapi import APIRouter, Body, Depends, HTTPException, status
from .security import require_auth

router = APIRouter(prefix="/vendors", tags=["vendors"])

@router.post("/train")
def train(body: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_auth)):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
