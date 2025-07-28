import re

def clean_vendor_name(raw):
    if not raw:
        return ""
    raw = raw.lower()
    raw = re.sub(r"(https?:\/\/)?(www\.)?", "", raw)
    raw = re.sub(r"(receipt.*|invoice.*|order.*|details.*)", "", raw)
    raw = re.sub(r"[^a-zA-Z0-9& ]", " ", raw)
    parts = raw.strip().split()
    if not parts:
        return ""
    return " ".join(parts[:5]).title()
