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
from semantic_extractor import extract_transactions
from collections import defaultdict

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

def extract_text_lines_with_ocr_structured(pdf_bytes):
    structured_lines = []

    try:
        with tempfile.TemporaryDirectory() as path:
            images = convert_from_bytes(pdf_bytes, output_folder=path)
            print(f"[INFO] OCR fallback: {len(images)} pages to process")

            for page_index, img in enumerate(images):
                ocr_result = pytesseract.image_to_data(img, output_type=Output.DICT)
                page_lines = defaultdict(list)

                for i in range(len(ocr_result["text"])):
                    word = ocr_result["text"][i].strip()
                    if not word:
                        continue

                    y = ocr_result["top"][i]
                    x = ocr_result["left"][i]

                    # Round y to group by row
                    line_y = round(y / 10) * 10
                    page_lines[line_y].append((x, word))

                for line_y in sorted(page_lines.keys()):
                    words = sorted(page_lines[line_y], key=lambda w: w[0])
                    line_text = " ".join(w[1] for w in words).strip()
                    if line_text:
                        structured_lines.append(line_text)

    except Exception as e:
        print(f"[ERROR] OCR structured extraction failed: {e}")

    print(f"[INFO] Extracted {len(structured_lines)} structured lines from OCR")
    return structured_lines

@app.post("/parse-pdf/")
async def parse_pdf(file: UploadFile = File(...)):
    try:
        if file.content_type != "application/pdf":
            raise ValueError("Only PDF files are supported.")

        raw_bytes = await file.read()

        if not isinstance(raw_bytes, (bytes, bytearray)):
            raise TypeError("Uploaded content is not byte-like")

        if not raw_bytes:
            raise ValueError("Uploaded file is empty")

        print("[INFO] Starting text extraction")
        file_buffer = BytesIO(raw_bytes)

        text_lines = extract_text_lines_from_pdf(file_buffer)
        print(f"[INFO] Extracted {len(text_lines)} lines from text layer")

        result = extract_transactions(text_lines)

        if not result.get("transactions"):
            print("[INFO] No transactions from text. Trying OCR fallback.")
            text_lines = extract_text_lines_with_ocr_structured(raw_bytes)
            print(f"[INFO] Extracted {len(text_lines)} lines from OCR")
            result = extract_transactions(text_lines)

        if not result.get("transactions"):
            print("[WARNING] Still no transactions found after OCR fallback")

        return JSONResponse(content=result)

    except Exception as e:
        print(f"[ERROR] parse_pdf failed: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=422)

@app.get("/")
def health_check():
    return {"status": "LumiLedger parser is online"}
