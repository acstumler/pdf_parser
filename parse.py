import io
import uuid
import pdfplumber
import re
from datetime import datetime

# Regex patterns
DATE_REGEX = re.compile(r'(\d{1,2}/\d{1,2}/\d{2,4})')
AMOUNT_REGEX = re.compile(r'\$?\(?-?\d{1,3}(?:,\d{3})*(?:\.\d{2})\)?')
SOURCE_REGEX = re.compile(r'Account Ending\s+2?-?(\d{4,6})', re.IGNORECASE)

EXCLUDE_KEYWORDS = [
    "interest charged", "payment due", "late fee", "fees",
    "minimum payment", "previous balance", "total", "avoid interest"
]

def clean_amount(value):
    value = value.replace('$', '').replace(',', '').replace('(', '-').replace(')', '')
    try:
        return float(value)
    except ValueError:
        return None

def is_valid_transaction(line, memo, amount):
    if not memo or len(memo) < 3:
        return False
    if any(k in line.lower() for k in EXCLUDE_KEYWORDS):
        return False
    if abs(amount) < 0.01:
        return False
    return True

def extract_transactions(pdf_bytes):
    transactions = []
    current_source = None

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                continue

            lines = text.split('\n')

            for line in lines:
                if not current_source:
                    src_match = SOURCE_REGEX.search(line)
                    if src_match:
                        current_source = f"American Express {src_match.group(1)}"

            i = 0
            while i < len(lines):
                line = lines[i].strip()
                date_match = DATE_REGEX.match(line)
                if date_match:
                    date_str = date_match.group(1).replace('-', '/').replace('.', '/')
                    try:
                        parsed_date = datetime.strptime(date_str, "%m/%d/%Y").strftime("%m/%d/%Y")
                    except ValueError:
                        i += 1
                        continue

                    memo_lines = [line]
                    amount = None

                    for j in range(1, 4):
                        if i + j < len(lines):
                            next_line = lines[i + j].strip()
                            amt_match = AMOUNT_REGEX.search(next_line)
                            if amt_match:
                                amount = clean_amount(amt_match.group(0))
                                if amount is not None:
                                    i = i + j
                                    break
                            else:
                                memo_lines.append(next_line)

                    memo = ' '.join(memo_lines)
                    memo_clean = re.sub(DATE_REGEX, '', memo)
                    memo_clean = re.sub(AMOUNT_REGEX, '', memo_clean)
                    memo_clean = re.sub(r'\s+', ' ', memo_clean).strip()

                    if is_valid_transaction(memo, memo_clean, amount):
                        transactions.append({
                            "id": str(uuid.uuid4()),
                            "date": parsed_date,
                            "memo": memo_clean,
                            "amount": amount,
                            "source": current_source or "",
                            "section": "",
                            "uploadedFrom": "",
                            "uploadedAt": None,
                            "account": "",
                            "classificationSource": "default"
                        })

                i += 1

    print(f"✅ Parsed {len(transactions)} transactions.")
    return { "transactions": transactions }
