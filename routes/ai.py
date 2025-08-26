from typing import Dict, Any
from fastapi import APIRouter, Body, Depends, HTTPException, status
from .security import require_auth
import os, json, urllib.request

router = APIRouter(prefix="/ai", tags=["ai"])

def _post_json(url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

@router.post("/embedding")
def embedding(payload: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_auth)):
    text = str(payload.get("text") or "")
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    url = "https://api.openai.com/v1/embeddings"
    body = {"model": "text-embedding-3-small", "input": text}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"}
    try:
        data = _post_json(url, body, headers)
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY)
    arr = (data.get("data") or [])
    if not arr:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY)
    vec = arr[0].get("embedding") or []
    return {"ok": True, "embedding": vec, "dims": len(vec)}
