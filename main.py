from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from universal_parser import extract_transactions
import shutil
import os

app = FastAPI()

# ✅ Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/parse-universal/")
async def parse_universal(file: UploadFile = File(...)):
    temp_path = "temp_uploaded.pdf"
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    transactions = extract_transactions(temp_path)

    # Clean up
    os.remove(temp_path)

    return {"transactions": transactions}
