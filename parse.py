import io
import pdfplumber
import re
from datetime import datetime

# Matches date formats like 10/25/2023, 10-25-23, or 10.25.23
DATE_REGEX = re.compile(r'\b(\d{1,2}[/-\.]\d{1,2}[/-\.]\d{2,4})\b')

def extract_transactions(pdf_bytes):
    transactions = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                print(f"[Page {page_num}] No text extracted.")
                continue

            print(f"\n--- Page {page_num} Content ---")
            print(text)

            lines = text.split('\n')
            for line in lines:
                print(f"[Line] {line}")

                match = DATE_REGEX.search(line)
                if not match:
                    continue

                date_str = match.group(1).replace('.', '/').replace('-', '/')
                try:
                    parsed_date = datetime.strptime(date_str, "%m/%d/%Y").strftime("%m/%d/%Y")
                except ValueError:
                    try:
                        parsed_date = datetime.strptime(date_str, "%m/%d/%y").strftime("%m/%d/%Y")
                    except ValueError:
                        print(f"Skipped invalid date format: {date_str}")
                        continue

                cleaned_line = line.replace('$', '').replace(',', '').strip()
                parts = cleaned_line.split()

                amount = None
                amount_index = None
                for i in range(len(parts) - 1, -1, -1):
                    try:
                        amount = float(parts[i])
                        amount_index = i
                        break
                    except ValueError:
                        continue

                if amount is None:
                    print(f"No valid amount found in line: {line}")
                    continue

                memo = ' '.join(parts[1:amount_index]) if amount_index > 1 else 'UNKNOWN'

                transaction = {
                    "date": parsed_date,
                    "memo": memo,
                    "amount": amount
                }

                print(f"Parsed transaction: {transaction}")
                transactions.append(transaction)

    print(f"\nTotal transactions parsed: {len(transactions)}")
    return transactions
