from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from parser_engine import parse_pdf  # Make sure this points to the correct parser function
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "LumiLedger PDF parser is live."}

@app.post("/parse-pdf/")
async def parse_pdf_endpoint(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        temp_filename = "temp_uploaded.pdf"
        with open(temp_filename, "wb") as f:
            f.write(file_bytes)

        print(f"📥 File written to {temp_filename}")
        results = parse_pdf(temp_filename)

        # Optional: clean up the temp file after parsing
        try:
            os.remove(temp_filename)
        except Exception as cleanup_err:
            print(f"⚠️ Could not delete temp file: {cleanup_err}")

        return { "transactions": results }

    except Exception as e:
        print(f"❌ Backend Exception: {e}")
        return { "error": str(e), "transactions": [] }
