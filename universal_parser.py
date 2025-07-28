import pdfplumber
import re
from datetime import datetime, timedelta
from utils.clean_vendor_name import clean_vendor_name
from utils.classifyTransaction import classifyTransaction

def extract_statement_period(text):
    match = re.search(
        r'(Closing Date|Period Ending|Statement Date)[\s:\n\r]*?(\d{1,2}/\d{1,2}/\d{2,4})',
        text,
        re.IGNORECASE,
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
    header_lines = "\n".join(text.splitlines()[:25])
    match = re.search(r'Account(?: Ending)?[\s:\-]*?(\d{4,6})', header_lines, re.IGNORECASE)
    return f"AMEX {match.group(1)}" if match else "Unknown"

def format_currency(amount):
    try:
        amount = float(amount)
        return f"(${abs(amount):,.2f})" if amount < 0 else f"${amount:,.2f}"
    except:
        return "$0.00"

def format_date(date_obj):
    return date_obj.strftime("%m/%d/%y")

def extract_visual_rows_v2(pdf_path):
    transactions = []

    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        start_date, end_date = extract_statement_period(full_text)
        source_account = extract_source_account(full_text)

        if not start_date or not end_date:
            return []

        for page in pdf.pages:
            words = page.extract_words(x_tolerance=1, y_tolerance=1)
            rows = {}

            for word in words:
                y = round(word["top"])
                rows.setdefault(y, []).append(word)

            for y_coord in sorted(rows.keys()):
                line = rows[y_coord]
                line.sort(key=lambda w: w["x0"])
                texts = [w["text"] for w in line]

                if len(texts) < 3:
                    continue

                date_match = re.match(r'\d{2}/\d{2}/\d{2,4}', texts[0])
                amount_match = re.search(r'\(?\$?[\d,.]+\)?$', texts[-1])

                if not date_match or not amount_match:
                    continue

                raw_date = texts[0]
                raw_amount = texts[-1]

                try:
                    date_obj = datetime.strptime(raw_date, "%m/%d/%Y")
                except ValueError:
                    try:
                        date_obj = datetime.strptime(raw_date, "%m/%d/%y")
                    except:
                        continue

                if not (start_date <= date_obj <= end_date):
                    continue

                try:
                    amount = float(raw_amount.replace("$", "").replace(",", "").replace("(", "-").replace(")", ""))
                except:
                    continue

                memo_text = " ".join(texts[1:-1])
                cleaned_memo = clean_vendor_name(memo_text)
                account = classifyTransaction(cleaned_memo)

                transactions.append({
                    "date": format_date(date_obj),
                    "memo": cleaned_memo,
                    "account": account,
                    "source": source_account,
                    "amount": format_currency(amount),
                })

    return transactions
