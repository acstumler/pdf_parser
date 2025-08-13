from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
import uvicorn

from classify_route import router as classify_router
from ml_route import router as ml_router
from memory_route import router as memory_router
from universal_parser import extract_transactions_from_bytes

app = FastAPI(title="LumiLedger Parser API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(classify_router, prefix="")
app.include_router(ml_router, prefix="")
app.include_router(memory_router, prefix="")

@app.post("/parse-universal-v2/")
async def parse_universal_v2(file: UploadFile = File(...)) -> JSONResponse:
    try:
        content = await file.read()
        txns, meta = extract_transactions_from_bytes(content)
        transactions = txns if isinstance(txns, list) else []
        payload = {
            "transactions": [
                {
                    "date": str(t.get("date", "")),
                    "memo_raw": str(t.get("memo_raw", "")),
                    "memo_clean": str(t.get("memo_clean", "")),
                    "amount": float(t.get("amount", 0.0)) if str(t.get("amount", "")).strip() != "" else 0.0,
                    "source_account": str(t.get("source_account", meta.get("source_account", ""))),
                }
                for t in transactions
            ],
            "source_account": str(meta.get("source_account", "")),
            "statement_end_date": str(meta.get("statement_end_date", "")),
            "errors": [],
        }
        return JSONResponse(payload)
    except Exception as e:
        return JSONResponse(
            {
                "transactions": [],
                "source_account": "",
                "statement_end_date": "",
                "errors": [str(e)],
            },
            status_code=200,
        )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
