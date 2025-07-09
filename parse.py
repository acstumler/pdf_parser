# pdf_parser/parse.py
import pdfplumber
import io
import re

def extract_transactions(file_bytes):
    transactions = []
    line_pattern = re.compile(r"^\d{2}/\d{2}/\d{2,4}\s+.*?\s+[-+]?\$?\d[\d,]*\.?\d{0,2}$")

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if is_valid_transaction_line(line, line_pattern):
                    parts = line.split()
                    try:
                        date = parts[0]
                        amount = parts[-1]
                        memo = ' '.join(parts[1:-1])
                        transactions.append({
                            "date": date,
                            "memo": memo,
                            "amount": amount
                        })
                    except Exception:
                        continue

    return transactions

def is_valid_transaction_line(line, pattern):
    return pattern.match(line)
