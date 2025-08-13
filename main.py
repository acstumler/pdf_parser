from fastapi import FastAPI, HTTPException, Header, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict
import pdfplumber
import io
import re

app = FastAPI(title="Lighthouse PDF Parser")

# Allow your production site and local dev
ALLOWED_ORIGINS = [
    "https://lighthouse-iq.vercel.app",
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=86400,
)

# ---------- Models ----------
class ClassifyRequest(BaseModel):
    memo: str
    amount: float
    date: Optional[str] = None
    source: Optional[str] = None
    source_type: Optional[str] = None

class ClassifyOut(BaseModel):
    account: str

class RememberVendorIn(BaseModel):
    memo: str
    account: str

class Ok(BaseModel):
    ok: bool = True

# ---------- Simple in-memory vendor memory ----------
MEMORY: Dict[str, str] = {}

def clean_vendor(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s

# ---------- File Upload Parsing ----------
@app.post("/parse-universal/")
async def parse_universal(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            raw_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        return {
            "ok": True,
            "filename": file.filename,
            "content_preview": raw_text[:1000]
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ---------- Vendor Memory ----------
@app.post("/remember-vendor", response_model=Ok)
def remember_vendor(req: RememberVendorIn, x_user_id: Optional[str] = Header(default="anonymous")):
    vendor = clean_vendor(req.memo)
    if not vendor or not req.account:
        raise HTTPException(status_code=400, detail="memo and account required")
    MEMORY[vendor] = req.account
    return Ok()
