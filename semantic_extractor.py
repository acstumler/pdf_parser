import uuid
import re
from datetime import datetime

# Match MM/DD/YYYY, MM-DD-YYYY, MM.DD.YY
DATE_REGEX = re.compile(r'^\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}')
AMOUNT_REGEX = re.compile(r'[-]?\$?[\d,]+\.\d{2}')

# Section types to exclude (summaries, metadata, etc.)
EXCLUDED_SECTIONS = [
    "SUMMARY", "REWARDS", "ACCOUNT INFO", "LATE FEES",
    "CREDIT SUMMARY", "MESSAGE", "NOTICES"
]

def is_probably_transaction(line: str, section: str = "") -> bool:
    line = line.strip()

    # 1. Must begin with a valid date pattern
    if not DATE_REGEX.match(line):
        return False

    # 2. Section must not be excluded
    if section and section.strip().upper() in EXCLUDED_SECTIONS:
        return False

    # 3. Line must include at least 4 words (date, memo, amount)
    parts = line.split()
    if len(parts) < 4:
        return False

    return True

def clean_memo(raw_memo: str) -> str:
    memo = raw_memo.strip()

    # Remove long numbers (store codes, transaction IDs)
    memo = re.sub(r'\b\d{5,}\b', '', memo)

    # Strip asterisks and normalize spacing
    memo = re.sub(r'[*]', '', memo)
    memo = re.sub(r'\s{2,}', ' ', memo)

    return memo.strip()

def extract_transactions(raw_pages, learned_memory):
    transactions = []

    for page in raw_pages:
        section = page.get("section", "")
        source = page.get("source", "")

        for line in page["lines"]:
            line = line.strip()

            # Must contain date and amount
            date_match = DATE_REGEX.search(line)
            amount_match = AMOUNT_REGEX.search(line)
            if not date_match or not amount_match:
                continue

            if not is_probably_transaction(line, section):
                continue

            # Parse date
            raw_date = date_match.group(0).replace('-', '/').replace('.', '/')
            try:
                parsed_date = datetime.strptime(raw_date, "%m/%d/%Y").strftime("%m/%d/%Y")
            except ValueError:
                try:
                    parsed_date = datetime.strptime(raw_date, "%m/%d/%y").strftime("%m/%d/%Y")
                except ValueError:
                    continue

            # Parse amount
            amt_str = amount_match.group(0).replace('$', '').replace(',', '')
            try:
                amount = float(amt_str)
            except ValueError:
                continue

            # Memo is text between date and amount
            date_pos = line.find(date_match.group(0))
            amt_pos = line.find(amount_match.group(0))
            raw_memo = line[date_pos + len(date_match.group(0)):amt_pos].strip()
            cleaned_memo = clean_memo(raw_memo)
            memo_key = cleaned_memo.lower()

            # Default classification
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
                "uploadedFrom": "",       # Populated in frontend
                "uploadedAt": None        # Populated in frontend
            })

    return { "transactions": transactions }
