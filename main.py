from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import status
from semantic_extractor import extract_transactions
import fitz  # PyMuPDF

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def extract_text_lines(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    all_lines = []
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            for l in b.get("lines", []):
                line_text = " ".join([s["text"] for s in l["spans"] if s["text"].strip()])
                if line_text:
                    all_lines.append(line_text)
    return all_lines

@app.get("/")
async def root():
    return {"message": "LumiLedger PDF Parser is running."}

@app.post("/parse-pdf/")
async def parse_pdf(file: UploadFile = File(...)):
    try:
        pdf_bytes = await file.read()
        text_lines = extract_text_lines(pdf_bytes)

        parsed = extract_transactions(text_lines)

        if parsed and parsed.get("transactions"):
            return parsed
        else:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={"error": "No transactions could be parsed from the PDF."}
            )
    except Exception as e:
        print("Exception during parsing:", e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal server error occurred while processing the PDF."}
        )
