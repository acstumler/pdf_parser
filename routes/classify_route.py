from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from ..services.classify_logic import classify_transaction

router = APIRouter()

class ClassificationRequest(BaseModel):
    memo: str
    user_id: Optional[str] = None

@router.post("/classify")
async def classify_endpoint(payload: ClassificationRequest, request: Request):
    try:
        result = await classify_transaction(payload.memo, payload.user_id)
        return {"account": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
