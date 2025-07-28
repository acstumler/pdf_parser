from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pdf_parser.universal_parser import extract_transactions
import fitz

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/parse-universal/")
async def parse_universal(file: UploadFile = File(...)):
    contents = await file.read()
    pdf = fitz.open(stream=contents, filetype="pdf")
    text = "\n".join([page.get_text() for page in pdf])
    parsed = extract_transactions(text)
    return {"transactions": parsed}
