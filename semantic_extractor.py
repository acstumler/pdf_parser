import uuid
import re
from datetime import datetime

# Match MM/DD/YYYY, MM-DD-YYYY, MM.DD.YY at the start of the line
DATE_REGEX = re.compile(r'^\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}')
AMOUNT_REGEX = re.compile(r'-?\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})')

EXCLUDED_SECTIONS = [
    "SUMMARY", "REWARDS", "ACCOUNT INFO", "LATE FEES",
    "CREDIT SUMMARY", "MESSAGE", "NOTICES"
]

EXCLUDE_MEMO_KEYWORDS = [
    "interest charged", "payment due", "late fee", "fees",
    "minimum payment", "previous balance", "total", "avoid interest"
]

def clean_memo(raw_memo: str) -> str:
    memo = raw_memo.strip()
    memo = re.sub(r'\b\d{5,}\b', '', memo)  # remove long numbers
    memo = re.sub(r'[*]', '', memo)
    memo = re.sub(r'\s{2,}', ' ', memo)
    return memo.strip()

def clean_amount(raw_amount: str) -> float | None:
    cleaned = raw_amount.replace('$', '').replace(',', '').replace('(', '-').replace(')', '')
    try:
        return float(cleaned)
    except ValueError:
        return None

def is_probably_transaction(line: str, section: str, amount: float, memo: str) -> bool:
    if not DATE_REGEX.match(line):
        return False
    if section and section.strip().upper() in EXCLUDED_SECTIONS:
        return False
    if any(k in memo.lower() for k in EXCLUDE_MEMO_KEYWORDS):
        return False
    if amount == 0 or len(memo.strip()) < 3:
        return False
    return True

def extract_transactions(raw_pages, learned_memory):
    transactions = []

    for page in raw_pages:
        section = page.get("section", "")
        source = page.get("source", "")

        lines = page["lines"]
        i = 0
        while i < len(lines):
            line_text = lines[i].get("text", "").strip()

            date_match = DATE_REGEX.match(line_text)
            if date_match:
                date_str = date_match.group(0).replace('-', '/').replace('.', '/')
                try:
                    parsed_date = datetime.strptime(date_str, "%m/%d/%Y").strftime("%m/%d/%Y")
                except ValueError:
                    i += 1
                    continue

                # Try to find the amount in the next 3 lines
                memo_lines = [line_text]
                amount = None
                for j in range(1, 4):
                    if i + j >= len(lines):
                        break
                    next_line = lines[i + j].get("text", "").strip()
                    amt_match = AMOUNT_REGEX.search(next_line)
                    if amt_match:
                        amount_val = clean_amount(amt_match.group(0))
                        if amount_val is not None:
                            amount = amount_val
                            i = i + j  # Advance past amount line
                            break
                    else:
                        memo_lines.append(next_line)

                full_memo = " ".join(memo_lines)
                stripped_memo = re.sub(DATE_REGEX, '', full_memo)
                stripped_memo = re.sub(AMOUNT_REGEX, '', stripped_memo)
                cleaned_memo = clean_memo(stripped_memo)

                if is_probably_transaction(full_memo, section, amount or 0, cleaned_memo):
                    memo_key = cleaned_memo.lower()
                    account = learned_memory.get(memo_key, "Unclassified")
                    classification_source = "learned_memory" if memo_key in learned_memory else "default"

                    transactions.append({
                        "id": str(uuid.uuid4()),
                        "date": parsed_date,
                        "memo": cleaned_memo,
                        "amount": amount,
                        "account": account,
                        "classificationSource": classification_source,
                        "source": source,
                        "section": section,
                        "uploadedFrom": "",
                        "uploadedAt": None
                    })

            i += 1

    return { "transactions": transactions }
