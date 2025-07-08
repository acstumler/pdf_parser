from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from parse import extract_transactions

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/parse-pdf")
async def parse_pdf(file: UploadFile = File(...)):
    contents = await file.read()
    transactions = extract_transactions(contents)
    return {"transactions": transactions}
