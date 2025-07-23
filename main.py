from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import fitz  # PyMuPDF
from semantic_extractor import extract_transactions

app = FastAPI()

# Allow frontend requests (update origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/parse-pdf/")
async def parse_pdf(file: UploadFile = File(...)):
    try:
        # Read PDF bytes
        contents = await file.read()

        # Use PyMuPDF to open the PDF
        pdf = fitz.open(stream=contents, filetype="pdf")

        # Extract transactions using semantic logic
        transactions = extract_transactions(pdf)

        return {"transactions": transactions}
    except Exception as e:
        return {"error": str(e)}
