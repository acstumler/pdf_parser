import uuid
import re
from datetime import datetime

# Match dates and amounts
DATE_REGEX = re.compile(r'\b(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})\b')
AMOUNT_REGEX = re.compile(r'[-]?\$?[\d,]+\.\d{2}')

def extract_transactions(raw_pages, learned_memory):
    transactions = []

    for page in raw_pages:
        for line in page["lines"]:
            # Validate required fields
            date_match = DATE_REGEX.search(line)
            amount_match = AMOUNT_REGEX.search(line)

            if not date_match or not amount_match:
                continue  # Skip lines that don’t contain a valid transaction

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

            # Memo = everything between date and amount
            date_pos = line.find(date_match.group(0))
            amt_pos = line.find(amount_match.group(0))
            memo_raw = line[date_pos + len(date_match.group(0)):amt_pos].strip()
            memo = ' '.join(memo_raw.split())

            memo_key = memo.lower()
            account = learned_memory.get(memo_key, "Unclassified")
            classification_source = "learned_memory" if memo_key in learned_memory else "default"

            transaction = {
                "id": str(uuid.uuid4()),
                "date": parsed_date,
                "memo": memo,
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
