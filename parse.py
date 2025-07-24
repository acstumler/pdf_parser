import io
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
from semantic_extractor import extract_transactions_from_text

def extract_with_pdfplumber(pdf_bytes):
    text_lines = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines = text.split('\n')
                text_lines.extend([line.strip() for line in lines if line.strip()])
    return text_lines

def extract_with_ocr(pdf_bytes):
    ocr_lines = []
    try:
        images = convert_from_bytes(pdf_bytes)
        for img in images:
            text = pytesseract.image_to_string(img)
            lines = text.split('\n')
            ocr_lines.extend([line.strip() for line in lines if line.strip()])
    except Exception as e:
        print(f"[OCR ERROR] {e}")
    return ocr_lines

def deduplicate_lines(lines):
    seen = set()
    unique = []
    for line in lines:
        fingerprint = line.lower().strip()
        if fingerprint not in seen:
            unique.append(line)
            seen.add(fingerprint)
    return unique

def extract_transactions(pdf_bytes):
    print("[INFO] Extracting with pdfplumber + OCR")
    text_lines = extract_with_pdfplumber(pdf_bytes)
    ocr_lines = extract_with_ocr(pdf_bytes)
    combined = text_lines + ocr_lines
    deduped = deduplicate_lines(combined)
    print(f"[INFO] Total combined lines: {len(deduped)}")
    return extract_transactions_from_text(deduped)
