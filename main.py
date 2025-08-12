# main.py
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
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
    allow_methods=["*"],          # includes OPTIONS for preflight
    allow_headers=["*"],          # e.g., Content-Type, Authorization
    max_age=86400,                # cache preflight for a day
)

# ---------- Models ----------
class ParseRequest(BaseModel):
    file_b64: str
    source_hint: Optional[str] = None

class ClassifyRequest(BaseModel):
    memo: str
    amount: float
    date: Optional[str] = None
    source: Optional[str] = None
    source_type: Optional[str] = None  # "Credit Card", "Bank", etc.

class ClassifyOut(BaseModel):
    account: str  # <- "5400 - Groceries"

class RememberVendorIn(BaseModel):
    memo: str
    account: str  # same "#### - Name" label you show in the UI

class Ok(BaseModel):
    ok: bool = True

# ---------- Simple in-memory vendor memory ----------
# key: cleaned vendor string -> account label
MEMORY: Dict[str, str] = {}

def clean_vendor(s: str) -> str:
    s = (s or "").lower()
    # strip numbers and punctuation, compress spaces
    s = re.sub(r"[^a-z\s]", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s

# ---------- Endpoints ----------
@app.post("/parse-universal/")
def parse_universal(req: ParseRequest):
    # stub — keep your real parsing here
    return {"ok": True, "source": "AMEX 61005"}

@app.post("/remember-vendor", response_model=Ok)
def remember_vendor(req: RememberVendorIn, x_user_id: Optional[str] = Header(default="anonymous")):
    vendor = clean_vendor(req.memo)
    if not vendor or not req.account:
        raise HTTPException(status_code=400, detail="memo and account required")
    MEMORY[vendor] = req.account
    return Ok()

@app.post("/classify-transaction", response_model=ClassifyOut)
@app.post("/classify-transaction/", response_model=ClassifyOut)
def classify_transaction(req: ClassifyRequest, x_user_id: Optional[str] = Header(default="anonymous")):
    """
    Return a single label exactly like your dropdown expects: '#### - Name'.
    Order of logic:
      1) If we've seen this vendor before, reuse.
      2) Very lightweight rules (stub — replace with your model later).
      3) Default to Uncategorized.
    """
    vendor = clean_vendor(req.memo)

    # 1) Memory first
    remembered = MEMORY.get(vendor)
    if remembered:
        return ClassifyOut(account=remembered)

    # 2) toy rules — replace with your classifier
    m = vendor
    if "kroger" in m:
        return ClassifyOut(account="5400 - Groceries")
    if "starbucks" in m or "mcdonald" in m or "restaurant" in m or "pizza" in m:
        return ClassifyOut(account="5330 - Meals & Entertainment")
    if "uber" in m or "nyct" in m or "amtrak" in m:
        return ClassifyOut(account="5700 - Travel")
    if "autozone" in m or "fuel" in m or "circle k" in m:
        return ClassifyOut(account="5200 - Auto & Transport")
    if "venmo" in m or "paypal" in m:
        return ClassifyOut(account="6998 - Miscellaneous")
    if "apple" in m or "software" in m:
        return ClassifyOut(account="6100 - Software & Subscriptions")

    # 3) fallback
    return ClassifyOut(account="6999 - Uncategorized Expense")
