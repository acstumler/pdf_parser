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
    memo = re.sub(r'[^\w\s&.,/-]', '', memo)
    stopwords = {"payment", "continued", "memo", "auth", "ref", "amount", "summary"}
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
            amount_val = None

            # Scan next 10 lines for memo and first amount
            block = all_lines[i:i+10]
            for line_candidate in block[1:]:
                amt_match = re.search(r'\$([\(\)\d,]+\.\d{2})', line_candidate)
                if amt_match and amount_val is None:
                    try:
                        amount_val = float(
                            amt_match.group(1).replace(",", "").replace("(", "-").replace(")", "")
                        )
                    except:
                        continue
                    line_candidate = line_candidate.replace(amt_match.group(0), '')
                memo_parts.append(line_candidate.strip())

            try:
                date_obj = datetime.strptime(date, "%m/%d/%Y")
            except ValueError:
                try:
                    date_obj = datetime.strptime(date, "%m/%d/%y")
                except:
                    i += 1
                    continue

            if not (start_date <= date_obj <= end_date) or amount_val is None:
                i += 1
                continue

            memo = clean_memo(" ".join(memo_parts))
            key = (date_obj.strftime("%m/%d/%Y"), memo, amount_val)
            if key in seen_keys:
                i += 1
                continue
            seen_keys.add(key)

            print(f"PARSED TRANSACTION — Date: {date_obj.strftime('%m/%d/%Y')} | Memo: {memo} | Amount: ${amount_val:.2f}")

            transactions.append({
                "date": date_obj.strftime("%m/%d/%Y"),
                "memo": memo,
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
