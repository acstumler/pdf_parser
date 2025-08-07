import os
import csv
import firebase_admin
from firebase_admin import credentials, firestore

# Load Firebase credentials from environment
import json
firebase_key_str = os.getenv("FIREBASE_KEY_JSON")
firebase_key_dict = json.loads(firebase_key_str)
cred = credentials.Certificate(firebase_key_dict)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Define export path
CSV_PATH = "ml_training_data.csv"

# Fetch all memory entries
ref = db.collection("vendor_memory")
docs = ref.stream()

rows = []

for doc in docs:
    data = doc.to_dict()
    vendor = data.get("vendor")
    account = data.get("account")
    if vendor and account:
        rows.append({
            "memo": vendor,
            "amount": "",     # No amount saved in memory yet
            "source": "",     # No source saved in memory yet
            "account": account
        })

# Write or append to CSV
with open(CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["memo", "amount", "source", "account"])
    if f.tell() == 0:
        writer.writeheader()
    writer.writerows(rows)

print(f"[Export] {len(rows)} vendor memory entries written to {CSV_PATH}")
