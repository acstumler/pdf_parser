from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import status
from semantic_extractor import extract_transactions as extract_semantic
# from parse import extract_transactions as fallback_extract  # fallback disabled
import fitz  # PyMuPDF

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def extract_text_blocks(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    all_lines = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            for l in b.get("lines", []):
                line_text = " ".join([s["text"] for s in l["spans"] if s["text"].strip()])
                if line_text:
                    all_lines.append(line_text)
    return all_lines

@app.get("/")
async def root():
    return {"message": "Lighthouse PDF Parser is running."}

@app.post("/parse-pdf/")
async def parse_pdf(file: UploadFile = File(...)):
    try:
        pdf_bytes = await file.read()
        text_lines = extract_text_blocks(pdf_bytes)

        print("DEBUG: Running semantic_extractor...")
        parsed = extract_semantic(text_lines, learned_memory={})

        if parsed and parsed.get("transactions"):
            print(f"Semantic parser returned {len(parsed['transactions'])} transactions")
            return parsed
        else:
            print("Semantic parser returned 0 transactions. Fallback disabled.")
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
