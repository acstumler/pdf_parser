from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from parse import extract_transactions

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
        results = extract_transactions(file_bytes)
        return results
    except Exception as e:
        return {"error": str(e)}
