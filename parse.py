# pdf_parser/parse.py
import pdfplumber
import io
import re

def extract_transactions(file_bytes):
    transactions = []
    metadata = {
        "bank": "Unknown",
        "account_suffix": "",
        "source": "Unknown"
    }

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            # Extract metadata once (bank name + last 4)
            if metadata["source"] == "Unknown":
                metadata = extract_metadata(text)

            line_pattern = re.compile(r"^\d{2}/\d{2}/\d{2,4}\s+.*?\s+[-+]?\$?\d[\d,]*\.?\d{0,2}$")
            lines = text.split('\n')

            for line in lines:
                line = line.strip()
                if line_pattern.match(line):
                    parts = line.split()
                    try:
                        date = parts[0]
                        amount = parts[-1]
                        memo = ' '.join(parts[1:-1])
                        transactions.append({
                            "date": date,
                            "memo": memo,
                            "amount": amount,
                            "source": metadata["source"]
                        })
                    except:
                        continue

    return transactions

def extract_metadata(text):
    bank = "American Express" if "American Express" in text else "Unknown"
    match = re.search(r"Account Ending (\d{4,5})", text)
    account_suffix = match.group(1) if match else ""
    label = f"{bank} {account_suffix}" if bank != "Unknown" and account_suffix else "Unknown"
    return {
        "bank": bank,
        "account_suffix": account_suffix,
        "source": label
    }
