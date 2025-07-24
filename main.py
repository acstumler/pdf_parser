from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from PyPDF2 import PdfReader
from semantic_extractor import extract_transactions_from_pdf

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow requests from any origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "LumiLedger PDF parser is live."}

@app.post("/parse-pdf/")
async def parse_pdf(file: UploadFile = File(...)):
    try:
        # Load PDF and extract text
        contents = await file.read()
        pdf_reader = PdfReader(file.file)
        text_blocks = []
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_blocks.append(page_text)

        transactions = extract_transactions_from_pdf(file, text_blocks)

        return {"transactions": transactions}
    except Exception as e:
        return {"error": str(e)}
