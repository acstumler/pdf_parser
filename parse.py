import pdfplumber
import io

def extract_transactions(file_bytes):
    results = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                for row in table[1:]:  # skip header
                    if len(row) >= 3:
                        date = row[0]
                        vendor = " ".join(row[1:-1]).strip()
                        try:
                            amount = float(row[-1].replace("$", "").replace(",", "").strip())
                        except:
                            amount = 0.0
                        results.append({
                            "date": date,
                            "vendor": vendor,
                            "amount": amount
                        })
    return results
