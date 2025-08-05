import os
import aiohttp
from firebase_admin import firestore, initialize_app

# Initialize Firestore only once
try:
    initialize_app()
except ValueError:
    pass  # Already initialized

db = firestore.client()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o"  # You can change this to "gpt-4.1" or another model if needed

async def classify_transaction(memo, user_id=None):
    # Step 1: Check Firestore for vendor memory
    if user_id:
        user_doc_ref = db.collection("vendor_memory").document(user_id)
        user_doc = user_doc_ref.get()
        if user_doc.exists:
            memory = user_doc.to_dict()
            for vendor, account in memory.items():
                if vendor.lower() in memo.lower():
                    return account  # Memory match found

    # Step 2: Fallback to OpenAI classification
    prompt = (
        f"Classify the following transaction memo into a GAAP-style account. "
        f"Return only the best-matching account name, no explanations or commentary.\n\n"
        f"Memo: \"{memo}\""
    )

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    json_payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "You are a bookkeeping assistant that classifies financial transactions."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }

    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.openai.com/v1/chat/completions", headers=headers, json=json_payload) as response:
            data = await response.json()
            try:
                return data["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError):
                return "Unclassified"
