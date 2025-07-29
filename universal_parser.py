import re
import pdfplumber
from datetime import datetime, timedelta
from utils.classifyTransaction import classifyTransaction
from utils.clean_vendor_name import clean_vendor_name

def extract_statement_period(text):
    match = re.search(
        r'(Closing Date|Statement Date|Period Ending)[\s:\n\r]*?(\d{1,2}/\d{1,2}/\d{2,4})',
        text,
        re.IGNORECASE
    )
    if match:
        try:
            closing_date = datetime.strptime(match.group(2), "%m/%d/%Y")
        except ValueError:
            try:
                closing_date = datetime.strptime(match.group(2), "%m/%d/%y")
            except:
                return None, None
        start_date = closing_date - timedelta(days=90)
        return start_date, closing_date
    return None, None

def extract_source_account(text):
    match = re.search(r'Account Ending[\s\-]*?(\d{4,6})', text, re.IGNORECASE)
    return f"AMEX {match.group(1)}" if match else "Unknown"

def clean_memo(memo):
    memo = memo.strip()
    memo = re.sub(r'\*+', '', memo)
    memo = re.sub(r'[^\w\s&./-]', '', memo)
    stopwords = {"payment", "continued", "memo", "auth", "ref", "amount", "summary"}
    words = [w for w in memo.split() if w.lower() not in stopwords]
    return " ".join(words).title()

def extract_transactions(pdf_path, start_date, end_date, source):
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
            raw_date = date_match.group(1)
            memo_parts = [line[len(raw_date):].strip()]
            amount_val = None

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
                date_obj = datetime.strptime(raw_date, "%m/%d/%Y")
            except ValueError:
                try:
                    date_obj = datetime.strptime(raw_date, "%m/%d/%y")
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

            classification = classifyTransaction(memo, amount_val).get("classification", "7090 - Uncategorized Expense")

            transactions.append({
                "date": date_obj.strftime("%m/%d/%y"),
                "memo": memo,
                "account": classification,
                "source": source,
                "amount": f"(${abs(amount_val):,2f})" if amount_val < 0 else f"${amount_val:,2f}"
            })
        i += 1

    return transactions

def extract_visual_rows_v2(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])

    start_date, end_date = extract_statement_period(full_text)
    if not start_date or not end_date:
        return []

    source = extract_source_account(full_text)
    return extract_transactions(pdf_path, start_date, end_date, source)
