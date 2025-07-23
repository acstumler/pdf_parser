import re
from pdfplumber.page import Page
from datetime import datetime


def extract_transactions_from_pdf(pdf, source_name="Unknown Source"):
    all_transactions = []

    print(f"[DEBUG] PDF has {len(pdf.pages)} pages.")

    for i, page in enumerate(pdf.pages):
        print(f"\n[DEBUG] --- Page {i + 1} ---")
        lines = page.extract_text().split("\n")

        for line in lines:
            print(f"[TEXT] {line}")
            parsed = try_parse_line(line)
            if parsed:
                print(f"[PARSED] {parsed}")
                parsed["source"] = source_name
                all_transactions.append(parsed)
            else:
                print(f"[SKIPPED] {line}")

    print(f"\n[RESULT] Total parsed transactions: {len(all_transactions)}")
    return all_transactions


def try_parse_line(line):
    # Example match: 11/22/23 CHICK FIL A LOUISVILLE KY $13.31
    match = re.match(r"(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+\$?(-?\(?\d+\.\d{2}\)?)", line)
    if not match:
        return None

    raw_date, raw_memo, raw_amount = match.groups()

    try:
        date_obj = parse_date(raw_date)
        amount = parse_amount(raw_amount)
        memo = clean_memo(raw_memo)

        return {
            "date": date_obj.strftime("%m/%d/%Y"),
            "memo": memo,
            "amount": amount,
            "account": "7090 - Uncategorized Expense",  # default
        }
    except Exception as e:
        print(f"[ERROR] Failed to parse line: {line} | {e}")
        return None


def parse_date(raw_date):
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw_date, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {raw_date}")


def parse_amount(raw):
    if "(" in raw and ")" in raw:
        raw = "-" + raw.strip("()")
    return round(float(raw.replace("$", "").replace(",", "")), 2)


def clean_memo(raw):
    raw = re.sub(r"\d{4,}", "", raw)  # remove long ID numbers
    raw = re.sub(r"[^\w\s&.-]", "", raw)  # remove weird punctuation
    raw = re.sub(r"\s{2,}", " ", raw)  # normalize whitespace
    return raw.strip().title()
