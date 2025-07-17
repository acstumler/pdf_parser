import io
import uuid
import pdfplumber
import re
from datetime import datetime

# Regex to match date, amount, and source patterns
DATE_REGEX = re.compile(r'\b(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})\b')
AMOUNT_REGEX = re.compile(r'[-]?\$?[\d,]+\.\d{2}')
SOURCE_REGEX = re.compile(r'Account Ending(?:\s+in)?\s+(\d{4,6})', re.IGNORECASE)

SECTION_HEADERS = ['Payments', 'Credits', 'New Charges', 'Other Fees', 'Interest Charged']

def extract_transactions(pdf_bytes):
    transactions = []
    current_section = None
    current_source = None

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                print(f"[Page {page_num}] No text found.")
                continue

            lines = text.split('\n')
            for i, line in enumerate(lines):
                line = line.strip()

                # Capture source (e.g. "Account Ending in 61005")
                if not current_source:
                    match = SOURCE_REGEX.search(line)
                    if match:
                        current_source = f"American Express {match.group(1)}"
                        print(f"Detected source: {current_source}")

                # Update section header
                if any(header in line for header in SECTION_HEADERS):
                    current_section = next((h for h in SECTION_HEADERS if h in line), current_section)
                    continue

                # Match date and amount
                date_match = DATE_REGEX.search(line)
                amount_match = AMOUNT_REGEX.search(line)

                if not date_match or not amount_match:
                    continue  # Not a valid transaction line

                # Parse date
                date_raw = date_match.group(1).replace('-', '/').replace('.', '/')
                try:
                    parsed_date = datetime.strptime(date_raw, "%m/%d/%Y").strftime("%m/%d/%Y")
                except ValueError:
                    try:
                        parsed_date = datetime.strptime(date_raw, "%m/%d/%y").strftime("%m/%d/%Y")
                    except ValueError:
                        continue

                # Parse amount
                amount_str = amount_match.group(0).replace('$', '').replace(',', '')
                try:
                    amount = float(amount_str)
                except ValueError:
                    continue

                # Build memo from parts between date and amount
                date_pos = line.find(date_match.group(0))
                amt_pos = line.find(amount_match.group(0))
                memo = line[date_pos + len(date_match.group(0)):amt_pos].strip()
                memo = ' '.join(memo.split())  # collapse extra spaces

                if not memo or len(memo) < 2:
                    memo = 'UNKNOWN'

                transaction = {
                    "id": str(uuid.uuid4()),
                    "date": parsed_date,
                    "memo": memo,
                    "amount": amount,
                    "source": current_source or "",
                    "section": current_section or "",
                    "uploadedFrom": "",
                    "uploadedAt": None,
                    "account": "",
                    "classificationSource": "default"
                }

                transactions.append(transaction)

    print(f"\nTotal transactions parsed: {len(transactions)}")
    return { "transactions": transactions }
