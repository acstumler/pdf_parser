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
            for page in pdf.pages:
                lines = page.extract_text().split('\n') if page.extract_text() else []
                for line in lines:
                    text_lines.append(line.strip())
    except Exception as e:
        print(f"Error during pdfplumber extraction: {e}")
    return text_lines

def extract_text_lines_with_ocr(file_buffer):
    text_lines = []
    try:
        with tempfile.TemporaryDirectory() as path:
            images = convert_from_bytes(file_buffer.getvalue(), output_folder=path)
            for img in images:
                ocr_result = pytesseract.image_to_data(img, output_type=Output.DICT)
                for i in range(len(ocr_result['text'])):
                    text = ocr_result['text'][i].strip()
                    top = ocr_result['top'][i]
                    if text:
                        text_lines.append({"text": text, "top": top})
    except Exception as e:
        print(f"Error during OCR fallback: {e}")
    return text_lines

@app.post("/parse-pdf/")
async def parse_pdf(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        file_buffer = BytesIO(file_content)

        # First try pdfplumber
        text_lines = extract_text_lines_from_pdf(file_buffer)

        result = extract_transactions(text_lines)

        if not result["transactions"]:
            print("[INFO] Falling back to OCR")
            file_buffer.seek(0)  # Reset buffer
            text_lines = extract_text_lines_with_ocr(file_buffer)
            result = extract_transactions(text_lines)

        return JSONResponse(content=result)

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=422)
