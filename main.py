from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import tempfile
from semantic_extractor import extract_transactions_from_pdf

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/parse-pdf/")
async def parse_pdf(file: UploadFile = File(...)):
    try:
        if file.content_type != "application/pdf":
            raise ValueError("Only PDF files are supported.")

        raw_bytes = await file.read()
        if not isinstance(raw_bytes, (bytes, bytearray)) or not raw_bytes:
            raise ValueError("Uploaded file must be a non-empty PDF.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(raw_bytes)
            tmp_path = tmp.name

        result = extract_transactions_from_pdf(tmp_path)
        return JSONResponse(content=result)

    except Exception as e:
        print(f"[ERROR] parse_pdf failed: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=422)

@app.get("/")
def health_check():
    return {"status": "LumiLedger parser is online"}
