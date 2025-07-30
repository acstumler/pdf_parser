import re

def clean_vendor_name(raw_memo):
    if not raw_memo:
        return "Unknown Vendor"

    memo = re.sub(r"[^A-Za-z0-9\s]", "", raw_memo)
    memo = re.sub(r"\b\d{4,}\b", "", memo)
    memo = re.sub(r"\b\w{1,2}\b", "", memo)
    memo = re.sub(r"\s{2,}", " ", memo).strip()

    words = memo.split()
    if not words:
        return "Unknown Vendor"

    condensed = " ".join(words[:3])
    return condensed.title()
