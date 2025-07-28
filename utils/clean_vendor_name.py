import re

def clean_vendor_name(memo):
    if not memo or not isinstance(memo, str):
        return "Unknown"

    memo = memo.lower()
    memo = re.sub(r'http\S+', '', memo)
    memo = re.sub(r'\d{4,}', '', memo)
    memo = re.sub(r'[^\w\s&.-]', '', memo)
    memo = re.sub(r'\b(?:continued|summary|payment|total|denotes|charge|date|amount|ky|ny|ca|llc|inc|pay over time)\b', '', memo)
    memo = re.sub(r'\s+', ' ', memo).strip()

    words = memo.split()
    if not words:
        return "Unknown"

    top = words[:4]
    return " ".join(w.capitalize() for w in top)
