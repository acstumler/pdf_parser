import os
import traceback
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

# Your existing imports
from parser_engine import detect_and_parse
from routes.classify_route import classify_router
from routes.ml_route import ml_router
from routes.memory_route import memory_router

load_dotenv()

# ---- Allowed CORS origins (explicit list; "*" + credentials is invalid) ----
def get_allowed_origins() -> List[str]:
    raw = os.getenv(
        "ALLOWED_ORIGINS",
        # Default to your Vercel app + local dev
        "https://lighthouse-iq.vercel.app,"
        "http://localhost:3000,"
        "http://127.0.0.1:3000"
    )
    return [o.strip() for o in raw.split(",") if o.strip()]

app = FastAPI()
# Avoid 307/308 redirects between `/path` and `/path/` which can break OPTIONS preflight
app.router.redirect_slashes = False

# ---- CORS ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=False,                # keep False so wildcard-like behavior is allowed
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)

# Universal OPTIONS handler so preflight never 405s
@app.options("/{full_path:path}")
async def preflight_handler(full_path: str) -> Response:
    return Response(status_code=204)

# ---- Health ----
@app.get("/health")
async def health():
    return {"status": "ok"}

# ---- Parse ----
@app.post("/parse-universal/")
async def parse_universal(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        parser = detect_and_parse(contents)
        transactions = parser.extract_transactions()
        return JSONResponse(content={"transactions": transactions})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ---- Routers (your existing endpoints, including /classify-transaction, /remember-vendor, etc.) ----
app.include_router(classify_router)
app.include_router(ml_router)
app.include_router(memory_router)
