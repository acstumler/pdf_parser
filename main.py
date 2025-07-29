from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import tempfile
from parser_engine import parse_and_classify as extract_transactions  # ✅ use new function name

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

    transactions = await extract_transactions(tmp_path)  # ✅ pass file path (str)
    return {"transactions": transactions}
