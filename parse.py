import io
import pdfplumber
from semantic_extractor import extract_transactions_from_pdf

def extract_transactions(pdf_bytes):
    with open("temp_statement.pdf", "wb") as f:
        f.write(pdf_bytes)

    result = extract_transactions_from_pdf("temp_statement.pdf")
    return result
