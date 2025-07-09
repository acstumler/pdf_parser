from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from parse import extract_transactions

app = FastAPI()

# ✅ Allow requests from your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://lighthouse-iq.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/parse-pdf")
async def parse_pdf(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        transactions = extract_transactions(contents)
        return {"transactions": transactions}
    except Exception as e:
        return {"error": "Failed to parse document", "details": str(e)}
