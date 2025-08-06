import os
import json
from pathlib import Path
import aiohttp
import firebase_admin
from firebase_admin import firestore, initialize_app, credentials
from openai import OpenAI

# Secure Firebase credential loading from environment variable
if not firebase_admin._apps:
    firebase_key_str = os.getenv("FIREBASE_KEY_JSON")
    firebase_key_dict = json.loads(firebase_key_str)
    cred = credentials.Certificate(firebase_key_dict)
    firebase_admin.initialize_app(cred)

# Firestore and OpenAI setup
db = firestore.client()
openai_client = OpenAI()

async def classify_transaction(vendor: str, user_id: str) -> str:
    # 1. Check user-trained memory
    user_map_ref = db.collection("user_vendor_map").document(user_id)
    user_doc = user_map_ref.get()
    if user_doc.exists:
        user_memory = user_doc.to_dict()
        if vendor in user_memory:
            return user_memory[vendor]

    # 2. Check global memory
    global_ref = db.collection("global_vendor_map").document("memory")
    global_doc = global_ref.get()
    if global_doc.exists:
        global_memory = global_doc.to_dict()
        if vendor in global_memory:
            return global_memory[vendor]

    # 3. Fallback to OpenAI classification
    prompt = (
        f"Given the vendor name '{vendor}', return the best matching account category "
        f"from a chart of accounts. Only return the account name, nothing else."
    )

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful accounting assistant."},
                {"role": "user", "content": prompt},
            ],
        )
        suggestion = response.choices[0].message.content.strip()

        # 4. Store suggestion in global memory
        global_ref.set({vendor: suggestion}, merge=True)
        return suggestion

    except Exception:
        return "Unclassified"
