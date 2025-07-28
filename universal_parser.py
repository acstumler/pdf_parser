import pdfplumber
import re
from datetime import datetime

def detect_statement_period(text):
    match = re.search(r'(Closing Date|Period Ending|Statement Date)[\s:]*?(\d{1,2}/\d{1,2}/\d{2,4})', text, re.IGNORECASE)
    if match:
        date_str = match.group(2)
        try:
            return datetime.strptime(date_str, "%m/%d/%y") if len(date_str.split("/")[-1]) == 2 else datetime.strptime(date_str, "%m/%d/%Y")
        except:
            return None
    return None

def extract_visual_rows_v2(pdf_path):
    transactions = []
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        statement_end = detect_statement_period(full_text)

        for page in pdf.pages:
            words = page.extract_words(x_tolerance=1, y_tolerance=1)

            # Group words by y-coordinate (bucketed)
            word_clusters = {}
            for word in words:
                y_key = round(word['top'] / 2.0) * 2.0
                word_clusters.setdefault(y_key, []).append(word)

            for y, row_words in sorted(word_clusters.items()):
                row_words.sort(key=lambda w: w['x0'])
                text_line = " ".join([w['text'] for w in row_words])

                # Apply anchor-based logic: starts with date, ends with amount
                date_match = re.match(r'^(\d{2}/\d{2}/\d{2,4})\b', text_line)
                amount_match = re.search(r'[-]?\(?\$?([\d,]+\.\d{2})\)?$', text_line)

                if date_match and amount_match:
                    raw_date = date_match.group(1)
                    raw_amount = amount_match.group(1)
                    memo = text_line.replace(raw_date, '').replace(raw_amount, '').strip()

                    try:
                        tx_date = datetime.strptime(raw_date, "%m/%d/%Y")
                    except ValueError:
                        try:
                            tx_date = datetime.strptime(raw_date, "%m/%d/%y")
                        except:
                            continue

                    if statement_end and tx_date > statement_end:
                        continue

                    try:
                        amount_val = float(raw_amount.replace(",", ""))
                        if "(" in text_line or "-" in text_line:
                            amount_val *= -1
                    except:
                        continue

                    transactions.append({
                        "Date": tx_date.strftime("%m/%d/%Y"),
                        "Memo": memo,
                        "Amount": round(amount_val, 2)
                    })

    return transactions
