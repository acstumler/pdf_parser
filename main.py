from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from universal_parser import extract_visual_rows_v2
import os

app = FastAPI()

# CORS policy
origins = [
    "http://localhost",
    "http://localhost:3000",
    "https://lumiledger.vercel.app",
    "https://www.lumiledger.com",
    "https://lumiledger.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/parse-universal/")
async def parse_universal_endpoint(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        temp_filename = "temp_uploaded.pdf"
        with open(temp_filename, "wb") as f:
            f.write(file_bytes)

        print(f"File written to {temp_filename}")
        transactions = extract_visual_rows_v2(temp_filename)

        try:
            os.remove(temp_filename)
        except Exception as cleanup_err:
            print(f"Could not delete temp file: {cleanup_err}")

        return {"transactions": transactions}

    except Exception as e:
        print(f"Backend Exception: {e}")
        return {"error": str(e), "transactions": []}
