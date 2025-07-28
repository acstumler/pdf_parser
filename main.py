from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List
import shutil
import os
from uuid import uuid4

from universal_parser import extract_transactions
from clean_vendor_name import clean_vendor_name

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/parse-universal/")
async def parse_universal(file: UploadFile = File(...)):
    try:
        # Save uploaded file temporarily
        contents = await file.read()
        temp_file_path = f"/tmp/{uuid4()}.pdf"
        with open(temp_file_path, "wb") as f:
            f.write(contents)

        transactions = extract_transactions(temp_file_path)

        # Clean vendor names post-classification
        for tx in transactions:
            tx["memo"] = clean_vendor_name(tx.get("memo", ""))

        os.remove(temp_file_path)
        return JSONResponse(content={"transactions": transactions})

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
