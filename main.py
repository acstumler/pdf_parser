from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from raw_parser import extract_pdf_lines
from semantic_extractor import extract_transactions
import json

app = FastAPI()

# Enable CORS for frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load memory from file (or start empty)
try:
    with open("learned_vendors.json", "r") as f:
        learned_memory = json.load(f)
except FileNotFoundError:
    learned_memory = {}

@app.post("/parse-pdf")
async def parse_pdf(file: UploadFile = File(...)):
    pdf_bytes = await file.read()

    raw_output = extract_pdf_lines(pdf_bytes)
    result = extract_transactions(raw_output, learned_memory)

    return result
