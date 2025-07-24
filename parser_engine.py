import re
from datetime import datetime, timedelta
import pdfplumber
from utils.clean_vendor_name import clean_vendor_name

def parse_amount(text):
    match = re.search(r"\$?(-?\(?\d{1,3}(?:,\d{3})*(?:\.\d{2})\)?)", text.replace(',', ''))
    if match:
        amt_str = match.group(1).replace('(', '-').replace(')', '').replace('$', '')
        try:
            return round(float(amt_str), 2)
        except ValueError:
            return None
    return None

def parse_date(text):
    match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', text)
    if match:
        raw = match.group(1)
        try:
            dt = datetime.strptime(raw, "%m/%d/%y") if len(raw.split('/')[-1]) == 2 else datetime.strptime(raw, "%m/%d/%Y")
            return dt.strftime("%m/%d/%Y")
        except ValueError:
            return None
    return None

def extract_closing_date(text):
    match = re.search(r"Closing Date[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})", text, re.IGNORECASE)
    if match:
        raw = match.group(1)
        try:
            dt = datetime.strptime(raw, "%m/%d/%y") if len(raw.split('/')[-1]) == 2 else datetime.strptime(raw, "%m/%d/%Y")
            return dt.strftime("%m/%d/%Y")
        except ValueError:
            return None
    return None

def extract_account_source(text):
    match = re.search(r'Account Ending(?: in)?\s*[\D]?(\d{4,6})', text, re.IGNORECASE)
    if match:
        return f"AMEX {match.group(1)}"
    if "American Express" in text:
        return "AMEX"
    return "Unknown"

def classify_account(memo, amount):
    # Placeholder for learned or AI-driven classification logic
    if amount and amount > 0:
        return "Unclassified Income"
    elif amount and amount < 0:
        return "Unclassified Expense"
    else:
        return "Other"

def extract_transactions_from_pdf(file_path):
    transactions = []
    full_text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"

    closing_date_str = extract_closing_date(full_text)
    source_account = extract_account_source(full_text)

    if not closing_date_str:
        print("[ERROR] No closing date found.")
        return []

    closing_date = datetime.strptime(closing_date_str, "%m/%d/%Y")
    start_date = closing_date - timedelta(days=90)

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            lines = page.extract_text().split('\n')
            for line in lines:
                if len(line.strip()) < 8:
                    continue

                date_str = parse_date(line)
                if not date_str:
                    continue

                txn_date = datetime.strptime(date_str, "%m/%d/%Y")
                if not (start_date <= txn_date <= closing_date):
                    continue

                amount = parse_amount(line)
                if amount is None:
                    continue

                memo = clean_vendor_name(line)
                account = classify_account(memo, amount)

                transactions.append({
                    "date": date_str,
                    "memo": memo,
                    "account": account,
                    "source": source_account,
                    "amount": f"${abs(amount):,.2f}" if amount >= 0 else f"(${abs(amount):,.2f})",
                    "statementClosingDate": closing_date_str
                })

    print(f"[INFO] Final parsed transactions: {len(transactions)}")
    return transactions
