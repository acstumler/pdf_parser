def extract_transactions(upload_file):
    transactions = []
    with pdfplumber.open(upload_file.file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                for row in table[1:]:  # skip header row
                    if len(row) >= 2:
                        date, vendor = row[0], row[1]
                        amount = row[-1].replace("$", "").replace(",", "").strip()
                        try:
                            amount = float(amount)
                        except ValueError:
                            amount = 0.0
                        transactions.append({
                            "date": date,
                            "vendor": vendor,
                            "amount": amount
                        })
    return transactions
