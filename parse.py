import io
import pdfplumber
import re
from datetime import datetime

# Matches MM/DD/YYYY or M/D/YY and variations like 10-25-23 or 10.25.23
DATE_REGEX = re.compile(r'\b(\d{1,2}[/-\.]\d{1,2}[/-\.]\d{2,4})\b')

def extract_transactions(pdf_bytes):
    transactions = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.split('\n')
            for line in lines:
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
                        continue

                cleaned_line = line.replace('$', '').replace(',', '').strip()
                parts = cleaned_line.split()

                # Look for the last float-like number as the amount
                amount = None
                for i in range(len(parts)-1, -1, -1):
                    try:
                        amount = float(parts[i])
                        amount_index = i
                        break
                    except ValueError:
                        continue

                if amount is None:
                    continue

                memo = ' '.join(parts[1:amount_index]) if amount_index > 1 else 'UNKNOWN'

                transaction = {
                    "date": parsed_date,
                    "memo": memo,
                    "amount": amount
                }
                transactions.append(transaction)

    return transactions
