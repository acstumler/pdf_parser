from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
import os, json, tempfile
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

@router.post("/demo-claim")
async def demo_claim(payload: DemoClaimIn, request: Request):
    _init_firebase_once()
    code_env = os.environ.get("DEMO_ACCESS_CODE", "").strip()
    if not code_env or payload.accessCode.strip() != code_env:
        raise HTTPException(status_code=400, detail="Invalid or expired access code")

    email_lc = payload.email.lower()
    try:
        user = auth.get_user_by_email(email_lc)
        uid = user.uid
        auth.update_user(uid, password=payload.password, display_name=payload.businessName)
    except auth.UserNotFoundError:
        user = auth.create_user(email=email_lc, password=payload.password, display_name=payload.businessName)
        uid = user.uid

    # custom claims to mark demo plan; front-end can read these later via ID token if desired
    try:
        auth.set_custom_user_claims(uid, {"planId": payload.planId, "testAccess": True})
    except Exception:
        pass

    # upsert a normal profile so backend/pages treat them like any user
    try:
        db = firestore.client()
        db.collection("users").document(uid).set(
            {
                "email": email_lc,
                "businessName": payload.businessName,
                "planId": payload.planId,
                "testAccess": True,
                "updatedAt": firestore.SERVER_TIMESTAMP,
                "createdAt": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
    except Exception:
        pass

    token = auth.create_custom_token(uid)
    return {"customToken": token.decode("utf-8") if isinstance(token, bytes) else token}
