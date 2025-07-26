import re
import pdfplumber
from datetime import datetime

def extract_statement_period(text):
    date_range_pattern = re.compile(
        r'([A-Za-z]{3,9})[\s\-–]+(\d{1,2})[\s\-–]+[–\-—][\s\-–]+([A-Za-z]{3,9})[\s\-–]+(\d{1,2}),\s*(\d{4})'
    )
    match = date_range_pattern.search(text)
    if match:
        try:
            month1, day1, month2, day2, year = match.groups()
            start_date = datetime.strptime(f"{month1} {day1} {year}", "%b %d %Y")
            end_date = datetime.strptime(f"{month2} {day2} {year}", "%b %d %Y")
            return start_date, end_date
        except:
            return None, None
    return None, None

def extract_source_account(text):
    match = re.search(r'Account Ending[\s\-]*?(\d{4,6})', text, re.IGNORECASE)
    if match:
        return f"AMEX {match.group(1)}"
    return "Unknown"

def clean_memo(memo):
    memo = memo.strip()
    memo = re.sub(r'\*+', '', memo)
    memo = re.sub(r'\d{4,}', '', memo)
    memo = re.sub(r'[^\w\s&.,/-]', '', memo)
    stopwords = {"aplpay", "tst", "store", "inc", "llc", "co", "payment", "continued", "memo", "auth", "ref"}
    words = [w for w in memo.split() if w.lower() not in stopwords]
    return " ".join(words).title()

def extract_transactions_visual(pdf_path, start_date=None, end_date=None, source="Unknown"):
    transactions = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=2, y_tolerance=1)
            lines_by_y = {}
            for word in words:
                y = round(word["top"])
                lines_by_y.setdefault(y, []).append(word)

            for y, words_on_line in sorted(lines_by_y.items()):
                sorted_words = sorted(words_on_line, key=lambda w: w["x0"])
                text_line = " ".join(w["text"] for w in sorted_words)
                match = re.search(
                    r'(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+(-?\(?[\d,]+\.\d{2}\)?)$',
                    text_line
                )
                if not match:
                    continue

                raw_date, raw_memo, raw_amount = match.groups()

                try:
                    date_obj = datetime.strptime(raw_date, "%m/%d/%Y")
                except ValueError:
                    try:
                        date_obj = datetime.strptime(raw_date, "%m/%d/%y")
                    except:
                        continue

                if start_date and end_date and not (start_date <= date_obj <= end_date):
                    continue

                amount_clean = raw_amount.replace(",", "").replace("(", "-").replace(")", "")
                try:
                    amount_float = float(amount_clean)
                except:
                    continue

                memo_cleaned = clean_memo(raw_memo)

                transactions.append({
                    "date": date_obj.strftime("%m/%d/%Y"),
                    "memo": memo_cleaned,
                    "account": "Unknown",
                    "source": source,
                    "amount": amount_float
                })

    return transactions

def parse_pdf(path):
    with open(path, "rb") as f:
        text = f.read().decode("latin1")  # fallback in case utf-8 fails

    start_date, end_date = extract_statement_period(text)
    source = extract_source_account(text)
    transactions = extract_transactions_visual(path, start_date, end_date, source)

    print("DEBUG: Returning parsed transactions")
    for t in transactions:
        print(t)

    return {"transactions": transactions}
