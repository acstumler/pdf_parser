from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from universal_parser import extract_transactions
import pdfplumber
import tempfile

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/parse-universal/")
async def parse_universal(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    with pdfplumber.open(tmp_path) as pdf:
        text_blocks = []
        for page in pdf.pages:
            lines = page.extract_text(y_tolerance=3, layout=True)
            if lines:
                text_blocks.extend(lines.split("\n"))

    transactions = extract_transactions(text_blocks)
    return {"transactions": transactions}
