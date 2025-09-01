from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timezone
import os, json, tempfile, bcrypt

import firebase_admin
from firebase_admin import auth, credentials, firestore

router = APIRouter()

class DemoClaimIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    businessName: str = Field(min_length=1)
    accessCode: str = Field(min_length=6)
    planId: str = "single-plan"

def _init_firebase_once():
    try:
        firebase_admin.get_app()
    except ValueError:
        cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH", "/etc/secrets/firebase-service-account.json").strip()
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            return
        raw_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        if raw_json:
            data = json.loads(raw_json)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
            tmp.write(json.dumps(data).encode("utf-8"))
            tmp.flush()
            cred = credentials.Certificate(tmp.name)
            firebase_admin.initialize_app(cred)
            return
        raise RuntimeError("Missing Firebase service account configuration")

def _matches_code(entered: str, stored: str) -> bool:
    """
    Accept either a bcrypt hash (preferred) or, if the stored value doesn't look like a bcrypt hash,
    treat it as plaintext (temporary safety-net).
    """
    if not stored:
        return False
    # bcrypt hashes start with $2a$/$2b$/$2y$
    if stored.startswith("$2"):
        try:
            return bcrypt.checkpw(entered.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False
    # fallback: plaintext equality (temporary)
    return entered == stored

@router.post("/demo-claim")
async def demo_claim(payload: DemoClaimIn, request: Request):
    _init_firebase_once()
    db = firestore.client()
    now = datetime.now(timezone.utc)

    # Query only by range to avoid composite index; filter 'active' in code
    codes_ref = db.collection("demo_codes")
    q = codes_ref.where("expires_at", ">", now)
    candidates = list(q.stream())

    match = None
    for snap in candidates:
        data = snap.to_dict() or {}
        if not data.get("active", False):
            continue
        stored = str(data.get("code_hash") or "")
        if _matches_code(payload.accessCode, stored):
            match = (snap, data)
            break

    if not match:
        raise HTTPException(status_code=400, detail="Invalid or expired access code")

    snap, data = match
    max_uses = int(data.get("max_uses", 1))
    uses = int(data.get("uses", 0))
    if uses >= max_uses:
        raise HTTPException(status_code=400, detail="Access code usage limit reached")

    # Consume use transactionally
    @firestore.transactional
    def _consume(tx):
        ref = snap.reference
        cur = ref.get(transaction=tx).to_dict() or {}
        if not cur.get("active", True):
            raise HTTPException(status_code=400, detail="Access code inactive")
        exp = cur.get("expires_at")
        if not exp or exp <= now:
            raise HTTPException(status_code=400, detail="Access code expired")
        cur_uses = int(cur.get("uses", 0))
        if cur_uses >= int(cur.get("max_uses", 1)):
            raise HTTPException(status_code=400, detail="Access code usage limit reached")
        tx.update(ref, {"uses": cur_uses + 1})

    _consume(db.transaction())

    # Create/update Firebase Auth user
    try:
        user = auth.get_user_by_email(payload.email)
        uid = user.uid
        auth.update_user(uid, password=payload.password, display_name=payload.businessName)
    except auth.UserNotFoundError:
        user = auth.create_user(
            email=payload.email,
            password=payload.password,
            display_name=payload.businessName
        )
        uid = user.uid

    # Upsert profile
    db.collection("users").document(uid).set(
        {
            "email": payload.email.lower(),
            "businessName": payload.businessName,
            "planId": payload.planId,
            "testAccess": True,
            "updatedAt": firestore.SERVER_TIMESTAMP,
            "createdAt": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )

    # Log claim
    db.collection("demo_claims").add(
        {
            "code_id": snap.reference.id,
            "email": payload.email.lower(),
            "businessName": payload.businessName,
            "planId": payload.planId,
            "claimed_at": firestore.SERVER_TIMESTAMP,
            "ip": request.client.host if request and request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "status": "success",
        }
    )

    token = auth.create_custom_token(uid)
    return {"customToken": token.decode("utf-8") if isinstance(token, bytes) else token}
