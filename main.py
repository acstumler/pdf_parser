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

def is_line_data_valid(lines):
    # Ensure at least 1 visually readable line has more than 10 characters
    for page in lines:
        for line in page.get("lines", []):
            if len(line.get("text", "").strip()) > 10:
                return True
    return False

@app.post("/parse-pdf")
async def parse_pdf(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        try:
            print("Attempting structured visual parsing...")
            raw_lines = extract_raw_lines(tmp_path)

            if not is_line_data_valid(raw_lines):
                print("Structured lines are invalid — falling back to OCR")
                raise ValueError("Invalid visual line extraction")

            parsed = semantic_extract(raw_lines, learned_memory={})
            if parsed and parsed["transactions"]:
                print("Parsed using structured visual parsing")
                return parsed

        except Exception as e:
            print("Structured parsing failed or invalid:", e)

        try:
            print("Attempting OCR fallback parser...")
            with open(tmp_path, "rb") as f:
                pdf_bytes = f.read()
            return fallback_extract(pdf_bytes)
        except Exception as e:
            print("OCR fallback failed:", e)
            return { "transactions": [] }

    finally:
        os.remove(tmp_path)

@app.get("/")
def root():
    return { "message": "LumiLedger PDF Parser is running." }
