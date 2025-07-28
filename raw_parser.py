import re
import pdfplumber
from datetime import datetime

def extract_transactions_multiline(pdf_path):
    transactions = []
    with pdfplumber.open(pdf_path) as pdf:
        lines = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines.extend(text.split('\n'))

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        date_match = re.match(r'^(\d{1,2}/\d{1,2}/\d{2,4})\b', line)

        if date_match:
            raw_date = date_match.group(1)
            memo_lines = []
            amount = None
            skip_keywords = ['total', 'summary', 'continued', 'pay over time', 'denotes']

            # Add current line (minus date) to memo
            remaining = line[len(raw_date):].strip()
            if remaining:
                memo_lines.append(remaining)

            j = i + 1
            while j < len(lines) and len(memo_lines) < 3:
                next_line = lines[j].strip().lower()
                if re.match(r'^\d{1,2}/\d{1,2}/\d{2,4}\b', next_line):
                    break
                if any(skip in next_line for skip in skip_keywords):
                    j += 1
                    continue

                amt_match = re.search(r'\$?(\(?-?\d[\d,]*\.\d{2}\)?)', lines[j])
                if amt_match and amount is None:
                    amt_raw = amt_match.group(1).replace(',', '').replace('(', '-').replace(')', '')
                    try:
                        amount = float(amt_raw)
                    except:
                        amount = 0.0
                else:
                    memo_lines.append(lines[j].strip())
                j += 1

            try:
                dt = datetime.strptime(raw_date, "%m/%d/%Y")
            except ValueError:
                try:
                    dt = datetime.strptime(raw_date, "%m/%d/%y")
                except:
                    i += 1
                    continue

            if amount is not None:
                transactions.append({
                    "date": dt.strftime("%m/%d/%y"),
                    "memo": " ".join(memo_lines),
                    "amount": amount
                })
            i = j
        else:
            i += 1
    return transactions
