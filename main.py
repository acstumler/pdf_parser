from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pdfplumber import open as open_pdf
import shutil
import os

from universal_parser import extract_transactions

app = FastAPI()

# ✅ CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://lighthouse-iq.vercel.app",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🧪 Health check route
@app.get("/")
def read_root():
    return {"message": "LumiLedger PDF Parser is live!"}

# 🔄 Parse PDF using the new universal parser
@app.post("/parse-universal/")
async def parse_universal(file: UploadFile = File(...)):
    temp_file_path = "temp_uploaded.pdf"
    
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    print(f"File written to {temp_file_path}")
    
    with open_pdf(temp_file_path) as pdf:
        transactions = extract_transactions(pdf)

    os.remove(temp_file_path)
    return {"transactions": transactions}
