from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import shutil
import os
from raw_parser import extract_raw_lines
from semantic_extractor import extract_transactions
import json

app = FastAPI()

# Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/parse-pdf")
async def parse_pdf(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        raw_lines = extract_raw_lines(tmp_path)

        # Placeholder for learned memory (could be passed by user in future)
        learned_memory = {}

        parsed = extract_transactions(raw_lines, learned_memory)
        return parsed
    finally:
        os.remove(tmp_path)

@app.get("/")
def root():
    return {"message": "LumiLedger PDF Parser is running."}
