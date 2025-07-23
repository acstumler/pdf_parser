from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from parse import extract_transactions  # Calls extract_transactions_from_text internally

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
        result = extract_transactions(raw_bytes)
        return JSONResponse(content=result)

    except Exception as e:
        print(f"[ERROR] parse_pdf failed: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=422)

@app.get("/")
def health_check():
    return {"status": "LumiLedger parser is online"}
