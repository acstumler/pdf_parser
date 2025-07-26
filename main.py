from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from parser_engine import extract_transactions
from io import BytesIO

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
async def parse_pdf(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        file_stream = BytesIO(file_bytes)
        file_stream.seek(0)
        results = extract_transactions(file_bytes)
        return { "transactions": results }
    except Exception as e:
        return { "error": str(e) }
