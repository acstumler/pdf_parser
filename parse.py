import pdfplumber

def extract_transactions(file_bytes):
    transactions = []

    with pdfplumber.open(file_bytes) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue

            for row in table[1:]:  # skip header
                if row and len(row) >= 3:
                    date, vendor, amount = row[:3]
                    try:
                        clean_amount = float(amount.replace("$", "").replace(",", ""))
                        transactions.append({
                            "date": date.strip(),
                            "vendor": vendor.strip(),
                            "amount": clean_amount
                        })
                    except Exception:
                        continue

    return transactions
