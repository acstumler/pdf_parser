import re

def clean_vendor_name(raw_memo):
    if not raw_memo:
        return "Unknown Vendor"

    # Split and isolate potential vendor segments
    parts = re.split(r"\d{2}/\d{2}/\d{2,4}|[T]\s|\d{4,}|[\$]", raw_memo)
    candidates = [part.strip() for part in parts if part.strip()]

    # Remove known noise words
    noise = ["detail", "denotes", "pay over time", "new charges", "thank you", "activity", "advance", "total"]
    cleaned = []

    for word in candidates:
        if not any(n in word.lower() for n in noise) and len(word) > 3:
            cleaned.append(word)

    return cleaned[0] if cleaned else raw_memo[:50]
