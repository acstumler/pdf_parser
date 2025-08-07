from fastapi import APIRouter, Request
from ml_classifier import classify_memo

ml_router = APIRouter()

@ml_router.post("/ml-classify")
async def ml_classify(req: Request):
    body = await req.json()
    memo = body.get("memo", "")

    if not memo:
        return {"error": "Memo is required."}

    try:
        classification = classify_memo(memo)
        return {"classification": classification}
    except Exception as e:
        return {"error": str(e)}
