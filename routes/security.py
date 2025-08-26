import os
from typing import List, Optional, Dict, Any
from fastapi import Header, HTTPException, status, FastAPI
from starlette.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import get_app, initialize_app

try:
    get_app()
except ValueError:
    initialize_app()

def _parse_allowed_origins() -> List[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "")
    items = [x.strip() for x in raw.split(",") if x.strip()]
    if items:
        return items
    return [
        "https://lighthouse-iq.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

def install_cors(app: FastAPI) -> None:
    origins = _parse_allowed_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
        expose_headers=["Content-Disposition"],
        max_age=86400,
    )

def _bearer_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return authorization.split(" ", 1)[1].strip()

def require_auth(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    try:
        token = _bearer_token(authorization)
        decoded = firebase_auth.verify_id_token(token, check_revoked=False)
        return {"uid": decoded.get("uid"), "token": decoded}
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

def optional_auth(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    try:
        token = _bearer_token(authorization)
        decoded = firebase_auth.verify_id_token(token, check_revoked=False)
        return {"uid": decoded.get("uid"), "token": decoded}
    except Exception:
        return None
