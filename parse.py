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
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue

            # Try to detect account/bank source from first 3 pages
            if metadata["source"] == "Unknown" and i < 3:
                metadata = extract_metadata(text)
                print(f"[DEBUG] Extracted metadata from page {i+1}:", metadata)

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

    print(f"[DEBUG] Sample parsed transactions: {transactions[:3]}")
    return transactions

def extract_metadata(text):
    bank = "American Express" if "American Express" in text or "AMEX" in text else "Unknown"

    # Try to match formats like: Account Ending 1005, Card Ending 1005, XXXX1005, or just 1005
    match = re.search(r"(?:Account (?:Ending|Number)?|Card Ending|XXXX)[^\d]{0,5}(\d{4,5})", text, re.IGNORECASE)
    if not match:
        match = re.search(r"\b(\d{4,5})\b", text)  # fallback: standalone 4-5 digit number

    account_suffix = match.group(1) if match else ""
    label = f"{bank} {account_suffix}" if bank != "Unknown" and account_suffix else "Unknown"

    return {
        "bank": bank,
        "account_suffix": account_suffix,
        "source": label
    }
