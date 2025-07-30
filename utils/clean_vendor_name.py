import re

def clean_vendor_name(raw_memo):
    if not raw_memo:
        return "Unknown Vendor"

    # Remove emails, URLs, and long digit strings
    memo = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "", raw_memo)
    memo = re.sub(r"https?://\S+", "", memo)
    memo = re.sub(r"\b\d{4,}\b", "", memo)

    # Replace non-alphanumeric characters with space
    memo = re.sub(r"[^A-Za-z0-9\s]", " ", memo)

    # Normalize spacing and trim
    memo = re.sub(r"\s{2,}", " ", memo).strip()

    # Capitalize intelligently
    return memo.title() if memo else "Unknown Vendor"
