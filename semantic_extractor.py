import uuid
import re
from datetime import datetime

# Regex to match date and amount
DATE_REGEX = re.compile(r'\b(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})\b')
AMOUNT_REGEX = re.compile(r'[-]?\$?[\d,]+\.\d{2}')

def clean_memo(raw_memo):
    memo = raw_memo.strip()

    # Remove long number IDs and store codes
    memo = re.sub(r'\b\d{5,}\b', '', memo)

    # Remove extra asterisks and normalize spaces
    memo = re.sub(r'[*]', '', memo)
    memo = re.sub(r'\s{2,}', ' ', memo)

    # Trim common locations or filler
    memo = re.sub(r'\b(LOUISVILLE|HUNT VALLEY|NEW YORK|KY|MD|CA|TN|TX|OH|IN)\b', '', memo, flags=re.IGNORECASE)

    # Normalize common vendor labels
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
            date_match = DATE_REGEX.search(line)
            amount_match = AMOUNT_REGEX.search(line)

            if not date_match or not amount_match:
                continue

            # Parse date
            raw_date = date_match.group(1).replace('-', '/').replace('.', '/')
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

            # Extract memo text
            date_pos = line.find(date_match.group(0))
            amt_pos = line.find(amount_match.group(0))
            raw_memo = line[date_pos + len(date_match.group(0)):amt_pos].strip()
            cleaned_memo = clean_memo(raw_memo)
            memo_key = cleaned_memo.lower()

            # Determine account from memory
            account = learned_memory.get(memo_key, "Unclassified")
            classification_source = "learned_memory" if memo_key in learned_memory else "default"

            transaction = {
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
            }

            transactions.append(transaction)

    return { "transactions": transactions }
