import re

def clean_vendor_name(raw_memo):
    if not raw_memo:
        return "Unknown Vendor"

    memo = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "", raw_memo)
    memo = re.sub(r"https?://\S+", "", memo)
    memo = re.sub(r"[^A-Za-z\s]", " ", memo)
    memo = re.sub(r"\s{2,}", " ", memo).strip()

    words = memo.split()
    cleaned = [word for word in words if len(word) > 2 and word.isalpha()]

    if not cleaned:
        return "Unknown Vendor"

    return " ".join(cleaned[:5]).title()
