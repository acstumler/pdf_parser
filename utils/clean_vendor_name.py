import re

def clean_vendor_name(raw_memo):
    if not raw_memo:
        return "Unknown Vendor"

    # Remove emails and domains first
    memo = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "", raw_memo)
    memo = re.sub(r"https?://\S+", "", memo)

    # Remove long digit strings
    memo = re.sub(r"\b\d{4,}\b", "", memo)

    # Remove symbols and collapse junk
    memo = re.sub(r"[^A-Za-z0-9\s]", " ", memo)
    memo = re.sub(r"\b\w{1,2}\b", "", memo)
    memo = re.sub(r"\s{2,}", " ", memo).strip()

    # Trim to top 3 clean tokens
    words = memo.split()
    if not words:
        return "Unknown Vendor"

    condensed = " ".join(words[:4])
    return condensed.title()
