from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import tempfile
from parser_engine import extract_visual_rows_v2 as extract_transactions

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://lighthouse-iq.vercel.app"],
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

    transactions = await extract_transactions(file)
    return {"transactions": transactions}
