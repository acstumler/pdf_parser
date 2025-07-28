import re
import pdfplumber
from datetime import datetime, timedelta

def extract_statement_period(text):
    closing_match = re.search(
        r'(Closing Date|Statement Date|Period Ending)[\s:\n\r]*?(\d{1,2}/\d{1,2}/\d{2,4})',
        text,
        re.IGNORECASE
    )
    if closing_match:
        date_str = closing_match.group(2)
        try:
            closing_date = datetime.strptime(date_str, "%m/%d/%y") if len(date_str.split("/")[-1]) == 2 else datetime.strptime(date_str, "%m/%d/%Y")
            start_date = closing_date - timedelta(days=90)
            print(f"DEBUG: Statement period = {start_date.date()} to {closing_date.date()}")
            return start_date, closing_date
        except Exception as e:
            print(f"ERROR parsing closing date: {e}")

    print("WARNING: No recognizable closing/period date found — skipping transactions.")
    return None, None

def extract_source_account(text):
    match = re.search(r'Account Ending[\s\-]*?(\d{4,6})', text, re.IGNORECASE)
    return f"AMEX {match.group(1)}" if match else "Unknown"

def clean_memo(memo):
    memo = memo.strip()
    memo = re.sub(r'\*+', '', memo)
    memo = re.sub(r'\d{4,}', '', memo)
    memo = re.sub(r'[^\w\s&.,/-]', '', memo)
    stopwords = {"aplpay", "tst", "store", "inc", "llc", "co", "payment", "continued", "memo", "auth", "ref"}
    words = [w for w in memo.split() if w.lower() not in stopwords]
    return " ".join(words).title()

def extract_transactions_multiline(pdf_path, start_date=None, end_date=None, source="Unknown"):
    if not start_date or not end_date:
        return []

    transactions = []
    seen_keys = set()

    with pdfplumber.open(pdf_path) as pdf:
        all_lines = []
        for page in pdf.pages:
            all_lines.extend(page.extract_text().split("\n"))

    i = 0
    while i < len(all_lines):
        line = all_lines[i].strip()
        date_match = re.match(r'^(\d{2}/\d{2}/\d{2,4})\b', line)
        if date_match:
            date = date_match.group(1)
            memo_parts = [line[len(date):].strip()]
            amount = None

            for j in range(i + 1, min(i + 6, len(all_lines))):
                next_line = all_lines[j].strip()
                amt_match = re.search(r'\$([\(\)\d,]+\.\d{2})$', next_line)
                if amt_match:
                    amount = amt_match.group(1)
                    i = j  # advance pointer past amount line
                    break
                else:
                    memo_parts.append(next_line)

            memo = " ".join(memo_parts).strip()
            if amount:
                try:
                    date_obj = datetime.strptime(date, "%m/%d/%Y")
                except ValueError:
                    try:
                        date_obj = datetime.strptime(date, "%m/%d/%y")
                    except:
                        i += 1
                        continue

                if not (start_date <= date_obj <= end_date):
                    i += 1
                    continue

                try:
                    amount_val = float(amount.replace(",", "").replace("(", "-").replace(")", ""))
                except:
                    i += 1
                    continue

                memo_cleaned = clean_memo(memo)
                key = (date_obj.strftime("%m/%d/%Y"), memo_cleaned, amount_val)
                if key in seen_keys:
                    i += 1
                    continue
                seen_keys.add(key)

                transactions.append({
                    "date": date_obj.strftime("%m/%d/%Y"),
                    "memo": memo_cleaned,
                    "account": "Unknown",
                    "source": source,
                    "amount": amount_val
                })
        i += 1

    return transactions

def parse_pdf(path):
    with pdfplumber.open(path) as pdf:
        full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])

    start_date, end_date = extract_statement_period(full_text)
    if not start_date or not end_date:
        return {"transactions": []}

    source = extract_source_account(full_text)
    transactions = extract_transactions_multiline(path, start_date, end_date, source)

    return {"transactions": transactions}
