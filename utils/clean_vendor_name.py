import re

def clean_vendor_name(memo_raw):
    # Uppercase and normalize
    memo = memo_raw.upper()

    # Remove phone numbers
    memo = re.sub(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "", memo)

    # Remove long numeric IDs or codes
    memo = re.sub(r"\b\d{5,}\b", "", memo)

    # Remove system artifacts (e.g., asterisks, @, hashes)
    memo = re.sub(r"[\"'*@#:]+", "", memo)

    # Replace slashes or pipes with space
    memo = re.sub(r"[-/\\|]+", " ", memo)

    # Collapse whitespace
    memo = re.sub(r"\s+", " ", memo)

    # Title-case and truncate
    memo = memo.strip().title()
    if len(memo.split()) > 6:
        memo = " ".join(memo.split()[:6])

    return memo
