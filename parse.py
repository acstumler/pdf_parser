import io
import pdfplumber
from semantic_extractor import extract_transactions_from_text

def extract_transactions(pdf_bytes):
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text_lines = []
        for page in pdf.pages:
            lines = page.extract_text().split('\n')
            text_lines.extend([line.strip() for line in lines if line.strip()])
    return extract_transactions_from_text(text_lines)
