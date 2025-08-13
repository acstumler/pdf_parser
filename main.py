from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
import uvicorn

# Use your existing universal parser implementation
from universal_parser import extract_transactions_from_bytes

app = FastAPI(title="LumiLedger Parser API")

# Open CORS (same as before)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

def _normalize_transactions(rows: List[Dict[str, Any]], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    source = str(meta.get("source_account", "")) if isinstance(meta, dict) else ""
    norm = []
    for r in (rows or []):
        # make sure all fields exist; frontend expects these keys
        norm.append({
            "date":          str(r.get("date", "")),
            "memo_raw":      str(r.get("memo_raw", "")),
            "memo_clean":    str(r.get("memo_clean", "") or r.get("memo", "")),
            "amount":        float(r.get("amount", 0) or 0),
            "source":        str(r.get("source", "") or r.get("source_account", "") or source),
            "source_account":str(r.get("source_account", "") or source),
            # pass-through optional account fields if present
            "account":       r.get("account", ""),
            "account_sub":   r.get("account_sub", ""),
            "account_main":  r.get("account_main", ""),
        })
    return norm

@app.post("/parse-universal/")
async def parse_universal(file: UploadFile = File(...)) -> JSONResponse:
    """
    RESTORES the original contract expected by the frontend:
    {
      "transactions": [...],
      "source": "",
      "source_account": "",
      "statement_end_date": "",
      "errors": []
    }
    """
    try:
        content = await file.read()
        txns, meta = extract_transactions_from_bytes(content)  # uses your existing parser
        transactions = _normalize_transactions(txns if isinstance(txns, list) else [], meta or {})
        payload = {
            "transactions": transactions,
            "source": str((meta or {}).get("source_account", "")),
            "source_account": str((meta or {}).get("source_account", "")),
            "statement_end_date": str((meta or {}).get("statement_end_date", "")),
            "errors": [],
        }
        return JSONResponse(payload)
    except Exception as e:
        # even on error, keep the same keys so the FE never crashes
        return JSONResponse({
            "transactions": [],
            "source": "",
            "source_account": "",
            "statement_end_date": "",
            "errors": [str(e)],
        }, status_code=200)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
