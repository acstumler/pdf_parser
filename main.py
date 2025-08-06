import os
from dotenv import load_dotenv
load_dotenv()

import traceback
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from strategies import STRATEGY_CLASSES
from services.pdf_utils import extract_text_from_pdf
from parser_engine import detect_and_parse
from routes.classify_route import classify_router

app = FastAPI()

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Main route for parsing uploaded PDFs
@app.post("/parse-universal/")
async def parse_universal(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        parser = detect_and_parse(contents)  # FIX: pass raw bytes
        transactions = parser.extract_transactions()
        return JSONResponse(content={"transactions": transactions})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Mount classification route
app.include_router(classify_router)
