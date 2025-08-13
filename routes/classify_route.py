from fastapi import APIRouter, Request
from pydantic import BaseModel
from services.classify_logic import classify_transaction

class TransactionInput(BaseModel):
    memo: str
    amount: float
    date: str
    source: str
    source_type: str | None = None

classify_router = APIRouter()

@classify_router.post("/classify-transaction/")
async def classify_transaction_endpoint(data: TransactionInput, request: Request):
    user_id = request.headers.get("X-User-ID", "anonymous")
    try:
        account = await classify_transaction(
            memo=data.memo,
            amount=data.amount,
            date=data.date,
            source=data.source,
            user_id=user_id,
            source_type=data.source_type,
        )
        if not account or not isinstance(account, str):
            account = "6999 - Uncategorized Expense"
        return {"account": account}
    except Exception as e:
        return {"account": "6999 - Uncategorized Expense", "error": str(e)}
