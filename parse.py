# pdf_parser/parse.py
import pdfplumber
import io

def extract_transactions(file_bytes):
    transactions = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.split('\n')
            for line in lines:
                if is_valid_transaction_line(line):
                    parts = line.strip().split()
                    try:
                        date = parts[0]
                        amount = parts[-1]
                        memo = ' '.join(parts[1:-1])
                        transactions.append({
                            "date": date,
                            "memo": memo,
                            "amount": amount
                        })
                    except Exception as e:
                        continue

    return transactions

def is_valid_transaction_line(line):
    return (
        '/' in line and
        any(char.isdigit() for char in line) and
        len(line.split()) >= 3 and
        not line.strip().lower().startswith('total')
    )
