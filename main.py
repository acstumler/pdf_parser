from fastapi import FastAPI, UploadFile, File, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
from universal_parser import extract_transactions_from_bytes

app = FastAPI(title="LumiLedger Parser API")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.router.redirect_slashes = False

@app.options("/parse-universal")
@app.options("/parse-universal/")
def _preflight_ok():
    return Response(status_code=204)

def _norm(rows: List[Dict[str, Any]], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    meta = meta or {}
    source = str(meta.get("source_account", ""))
    out = []
    for r in rows or []:
        out.append({
            "date": str(r.get("date", "")),
            "memo_raw": str(r.get("memo_raw", "")),
            "memo_clean": str(r.get("memo_clean", "") or r.get("memo", "")),
            "amount": float(r.get("amount", 0) or 0),
            "source": str(r.get("source", "") or r.get("source_account", "") or source),
            "source_account": str(r.get("source_account", "") or source),
            "account": r.get("account", ""),
            "account_sub": r.get("account_sub", ""),
            "account_main": r.get("account_main", ""),
        })
    return out

@app.post("/parse-universal")
@app.post("/parse-universal/")
async def parse_universal(file: UploadFile = File(...)):
    try:
        data = await file.read()
        rows, meta = extract_transactions_from_bytes(data)
        txns = _norm(rows if isinstance(rows, list) else [], meta or {})
        return JSONResponse({
            "transactions": txns,
            "source": str((meta or {}).get("source_account", "")),
            "source_account": str((meta or {}).get("source_account", "")),
            "statement_end_date": str((meta or {}).get("statement_end_date", "")),
            "errors": [],
        })
    except Exception as e:
        return JSONResponse({
            "transactions": [],
            "source": "",
            "source_account": "",
            "statement_end_date": "",
            "errors": [str(e)],
        }, status_code=200)
