from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
from pytesseract import Output
import tempfile
import os
from io import BytesIO
from parse import extract_transactions

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def extract_text_lines_from_pdf(file_buffer):
    text_lines = []
    try:
        with pdfplumber.open(file_buffer) as pdf:
            print(f"[INFO] PDF has {len(pdf.pages)} pages")
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    lines = text.split('\n')
                    for line in lines:
                        if line.strip():
                            text_lines.append(line.strip())
    except Exception as e:
        print(f"[ERROR] pdfplumber extraction failed: {e}")
    return text_lines

def extract_text_lines_with_ocr(file_buffer):
    text_lines = []
    try:
        with tempfile.TemporaryDirectory() as path:
            images = convert_from_bytes(file_buffer.getvalue(), output_folder=path)
            print(f"[INFO] OCR fallback: {len(images)} pages to process")
            for img in images:
                ocr_result = pytesseract.image_to_data(img, output_type=Output.DICT)
                for i in range(len(ocr_result['text'])):
                    text = ocr_result['text'][i].strip()
                    top = ocr_result['top'][i]
                    if text:
                        text_lines.append({"text": text, "top": top})
    except Exception as e:
        print(f"[ERROR] OCR fallback failed: {e}")
    return text_lines

@app.post("/parse-pdf/")
async def parse_pdf(file: UploadFile = File(...)):
    try:
        raw_bytes = await file.read()

        if isinstance(raw_bytes, list):
            raw_bytes = b"".join(raw_bytes)
        elif not isinstance(raw_bytes, (bytes, bytearray)):
            raise ValueError("Uploaded content is not byte-like")

        if not raw_bytes:
            raise ValueError("Uploaded file is empty")

        file_buffer = BytesIO(raw_bytes)

        print("[INFO] Starting text extraction")
        text_lines = extract_text_lines_from_pdf(file_buffer)
        print(f"[INFO] Extracted {len(text_lines)} lines from text layer")

        result = extract_transactions(text_lines)

        if not result.get("transactions"):
            print("[INFO] No transactions from text. Trying OCR fallback.")
            text_lines = extract_text_lines_with_ocr(BytesIO(raw_bytes))
            print(f"[INFO] Extracted {len(text_lines)} lines from OCR")
            result = extract_transactions(text_lines)

        if not result.get("transactions"):
            print("[WARNING] Still no transactions found after OCR fallback")

        return JSONResponse(content=result)

    except Exception as e:
        print(f"[ERROR] parse_pdf failed: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=422)
