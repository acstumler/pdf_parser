# main.py
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import shutil
import os
from parse import extract_transactions  # <- now using pdfplumber-based parser

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
        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()

        parsed = extract_transactions(pdf_bytes)
        return parsed
    finally:
        os.remove(tmp_path)

@app.get("/")
def root():
    return {"message": "LumiLedger PDF Parser is running."}
