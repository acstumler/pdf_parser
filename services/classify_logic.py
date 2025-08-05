import os
import json
import aiohttp
from firebase_admin import credentials, firestore, initialize_app
from openai import OpenAI

# Load Firebase service account credentials
FIREBASE_CRED_PATH = os.path.join(os.path.dirname(__file__), '../firebase_key.json')

cred = credentials.Certificate(FIREBASE_CRED_PATH)
initialize_app(cred)
db = firestore.client()

# Access environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai = OpenAI(api_key=OPENAI_API_KEY)

async def classify_transaction(memo, user_id=None):
    vendor = memo.strip().lower()
    if not vendor:
        return "Uncategorized"

    # Try: check if user has a classification saved
    if user_id:
        user_ref = db.collection("vendor_memory").document(user_id).collection("vendors").document(vendor)
        doc = user_ref.get()
        if doc.exists:
            return doc.to_dict().get("account", "Uncategorized")

    # AI fallback
    prompt = f"What chart of account category best fits this vendor name: '{memo}'?"
    try:
        response = await openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        result = response.choices[0].message.content.strip()
    except Exception:
        result = "Uncategorized"

    # Save classification for future reference if user_id provided
    if user_id:
        user_ref.set({"account": result}, merge=True)

    return result
