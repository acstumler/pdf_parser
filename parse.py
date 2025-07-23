import fitz  # PyMuPDF
import pdfplumber
from fastapi import UploadFile
from typing import List
from semantic_extractor import extract_transactions

async def parse_pdf(file: UploadFile) -> List[dict]:
    # Use pdfplumber to extract text from all pages
    all_lines = []
    with pdfplumber.open(file.file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                all_lines.extend(lines)

    transactions = extract_transactions(all_lines)
    return transactions
