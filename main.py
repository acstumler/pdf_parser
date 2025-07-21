from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import shutil
import os

from raw_parser import extract_raw_lines
from semantic_extractor import extract_transactions as semantic_extract
from parse import extract_transactions as fallback_extract  # OCR fallback

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
        # Step 1: Attempt structured visual parsing
        try:
            raw_lines = extract_raw_lines(tmp_path)
            parsed = semantic_extract(raw_lines, learned_memory={})
            if parsed and parsed["transactions"]:
                print("Parsed using structured visual parsing")
                return parsed
        except Exception as e:
            print("Structured parsing failed:", e)

        # Step 2: Fallback to OCR-based parsing
        try:
            print("Attempting OCR fallback parser")
            with open(tmp_path, "rb") as f:
                pdf_bytes = f.read()
            return fallback_extract(pdf_bytes)
        except Exception as e:
            print("OCR fallback also failed:", e)
            return { "transactions": [] }

    finally:
        os.remove(tmp_path)

@app.get("/")
def root():
    return { "message": "LumiLedger PDF Parser is running." }
