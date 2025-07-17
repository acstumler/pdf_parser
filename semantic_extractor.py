import uuid
import re
from datetime import datetime

# Match date formats like MM/DD/YYYY, MM-DD-YYYY, MM.DD.YY
DATE_REGEX = re.compile(r'\b(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})\b')
AMOUNT_REGEX = re.compile(r'[-]?\$?[\d,]+\.\d{2}')

# Phrases that indicate a line should be excluded
BLOCKLIST_PHRASES = [
    "late fee", "due date", "payment due", "total interest",
    "total fees charged", "statement balance", "closing date",
    "ending balance", "past due", "minimum payment", "new balance"
]

# Phrases that imply a real transaction, charge, or payment
VENDOR_KEYWORDS = [
    "payment", "purchase", "restaurant", "store", "apple",
    "paypal", "venmo", "uber", "auto", "liquors", "grill",
    "hotel", "subway", "walgreens", "interest", "charge",
    "chipotle", "market", "fuel", "circle k", "amazon",
    "delivery", "shell", "service", "target", "kroger",
    "transaction", "food", "gas", "mobile", "mcdonald", "starbucks"
]

def is_probably_transaction(line: str) -> bool:
    lower = line.lower().strip()

    # Must start with a date
    if not re.match(r'^\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}', line):
        return False

    # Block lines with unwanted metadata
    if any(phrase in lower for phrase in BLOCKLIST_PHRASES):
        return False

    # Keep lines that mention payments or interest directly
    if "payment" in lower or "interest" in lower:
        return True

    # Or that include known vendor terms
    return any(keyword in lower for keyword in VENDOR_KEYWORDS)

def clean_memo(raw_memo: str) -> str:
    memo = raw_memo.strip()

    # Remove store IDs or trailing long numbers
    memo = re.sub(r'\b\d{5,}\b', '', memo)

    # Normalize punctuation and spacing
    memo = re.sub(r'[*]', '', memo)
    memo = re.sub(r'\s{2,}', ' ', memo)

    # Remove common location info
    memo = re.sub(r'\b(LOUISVILLE|NEW YORK|KY|CA|TX|MD|NC|IN|TN|OH)\b', '', memo, flags=re.IGNORECASE)

    # Clean up known vendor names
    memo = memo.replace("APPLE.COM/BILL", "Apple")
    memo = memo.replace("PAYPAL", "PayPal")
    memo = memo.replace("VENMO", "Venmo")
    memo = memo.replace("APL*PAY", "ApplePay")
    memo = memo.replace("APL PAY", "ApplePay")
    memo = memo.replace("APPLE ONLINE STORE", "Apple")

    return memo.strip()

def extract_transactions(raw_pages, learned_memory):
    transactions = []

    for page in raw_pages:
        for line in page["lines"]:
            # Extract date and amount
            date_match = DATE_REGEX.search(line)
            amount_match = AMOUNT_REGEX.search(line)
            if not date_match or not amount_match:
                continue

            if not is_probably_transaction(line):
                continue

            raw_date = date_match.group(1).replace('-', '/').replace('.', '/')
            try:
                parsed_date = datetime.strptime(raw_date, "%m/%d/%Y").strftime("%m/%d/%Y")
            except ValueError:
                try:
                    parsed_date = datetime.strptime(raw_date, "%m/%d/%y").strftime("%m/%d/%Y")
                except ValueError:
                    continue

            amt_str = amount_match.group(0).replace('$', '').replace(',', '')
            try:
                amount = float(amt_str)
            except ValueError:
                continue

            # Extract and clean memo
            date_pos = line.find(date_match.group(0))
            amt_pos = line.find(amount_match.group(0))
            raw_memo = line[date_pos + len(date_match.group(0)):amt_pos].strip()
            cleaned_memo = clean_memo(raw_memo)
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
                "source": page.get("source", ""),
                "section": page.get("section", ""),
                "uploadedFrom": "",
                "uploadedAt": None
            })

    return { "transactions": transactions }
