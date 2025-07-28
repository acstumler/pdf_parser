import re
import pdfplumber
from datetime import datetime, timedelta

def extract_statement_period(text):
    closing_match = re.search(r'Closing Date\s+(\d{1,2}/\d{1,2}/\d{2,4})', text, re.IGNORECASE)
    if closing_match:
        date_str = closing_match.group(1)
        try:
            if len(date_str.split("/")[-1]) == 2:
                closing_date = datetime.strptime(date_str, "%m/%d/%y")
            else:
                closing_date = datetime.strptime(date_str, "%m/%d/%Y")
            start_date = closing_date - timedelta(days=90)
            print(f"DEBUG: Statement period = {start_date.date()} to {closing_date.date()}")
            return start_date, closing_date
        except Exception as e:
            print(f"ERROR parsing closing date: {e}")
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
    seen_keys = set()

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
                    r'^(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+\$?(-?\(?[\d,]+\.\d{2}\)?)$',
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

                # Enforce 90-day period filtering
                if start_date and end_date and not (start_date <= date_obj <= end_date):
                    continue

                amount_clean = raw_amount.replace(",", "").replace("(", "-").replace(")", "")
                try:
                    amount_float = float(amount_clean)
                except:
                    continue

                memo_cleaned = clean_memo(raw_memo)

                # Deduplication key
                key = (date_obj.strftime("%m/%d/%Y"), memo_cleaned, amount_float)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                transactions.append({
                    "date": date_obj.strftime("%m/%d/%Y"),
                    "memo": memo_cleaned,
                    "account": "Unknown",
                    "source": source,
                    "amount": amount_float
                })

    return transactions

def parse_pdf(path):
    with pdfplumber.open(path) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() or ""

    start_date, end_date = extract_statement_period(full_text)
    source = extract_source_account(full_text)
    transactions = extract_transactions_visual(path, start_date, end_date, source)

    return {"transactions": transactions}
