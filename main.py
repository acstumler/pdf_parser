# main.py
import os
from dotenv import load_dotenv

load_dotenv()

import traceback
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from parser_engine import detect_and_parse
from routes.classify_route import classify_router
from routes.ml_route import ml_router
from routes.memory_route import memory_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/parse-universal/")
async def parse_universal(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        parser = detect_and_parse(contents)
        transactions = parser.extract_transactions()
        return JSONResponse(content={"transactions": transactions})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(classify_router)
app.include_router(ml_router)
app.include_router(memory_router)
