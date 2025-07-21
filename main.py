from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import shutil
import os

from raw_parser import extract_raw_lines
from semantic_extractor import extract_transactions as semantic_extract
from parse import extract_transactions as fallback_extract

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def is_line_data_valid(lines):
    print("Checking visual line integrity...")
    valid_count = 0
    for page in lines:
        for line in page.get("lines", []):
            if len(line.get("text", "").strip()) > 10:
                valid_count += 1
    print(f"Found {valid_count} valid visual lines")
    return valid_count > 5

@app.post("/parse-pdf")
async def parse_pdf(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        try:
            print(">>> Starting structured visual parsing (raw_parser.py)")
            raw_lines = extract_raw_lines(tmp_path)

            print(">>> Sample lines from visual parser:")
            for page in raw_lines[:1]:
                for line in page.get("lines", [])[:3]:
                    print("Line:", line.get("text"))

            if not is_line_data_valid(raw_lines):
                print(">>> Visual line structure insufficient — fallback triggered")
                raise ValueError("Structured visual content too weak")

            parsed = semantic_extract(raw_lines, learned_memory={})
            print(f">>> Structured parsing found {len(parsed['transactions'])} transactions")

            if parsed["transactions"]:
                return parsed

        except Exception as e:
            print(">>> Structured parsing failed or invalid:", e)

        try:
            print(">>> Attempting OCR fallback (parse.py)")
            with open(tmp_path, "rb") as f:
                pdf_bytes = f.read()
            parsed = fallback_extract(pdf_bytes)
            print(f">>> OCR parsing returned {len(parsed['transactions'])} transactions")
            return parsed
        except Exception as e:
            print(">>> OCR fallback also failed:", e)
            return { "transactions": [] }

    finally:
        os.remove(tmp_path)

@app.get("/")
def root():
    return { "message": "LumiLedger PDF Parser is running." }
