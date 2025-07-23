import pdfplumber
import re
from dateutil import parser
from datetime import datetime, timedelta
from utils.clean_vendor_name import clean_vendor_name

def extract_source_account(text_lines):
    for line in text_lines:
        if "account ending" in line.lower():
            match = re.search(r"account ending\s*(\d{4,6})", line, re.IGNORECASE)
            if match:
                return f"AMEX {match.group(1)}"
    return "Unknown Source"

def group_words_by_y(words, y_tolerance=3):
    lines = {}
    for word in words:
        y = round(word['top'])
        line_key = next((key for key in lines if abs(key - y) <= y_tolerance), y)
        lines.setdefault(line_key, []).append(word)
    return [sorted(line, key=lambda w: w['x0']) for _, line in sorted(lines.items())]

def parse_amount(text):
    try:
        text = text.replace("$", "").replace(",", "").strip()
        return float(text)
    except:
        return None

def extract_date(text):
    try:
        return parser.parse(text).strftime("%m/%d/%Y")
    except:
        return None

def extract_transactions_from_pdf(file_path):
    transactions = []
    seen_fingerprints = set()
    with pdfplumber.open(file_path) as pdf:
        raw_text = []
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                raw_text += extracted.split('\n')

        source_account = extract_source_account(raw_text)

        for page in pdf.pages:
            words = page.extract_words(extra_attrs=["x0", "top", "x1", "bottom"])
            lines = group_words_by_y(words)

            for line in lines:
                if len(line) < 3:
                    continue

                left = line[0]['text']
                right = line[-1]['text']
                middle = " ".join(w['text'] for w in line[1:-1])

                date = extract_date(left)
                amount = parse_amount(right)
                memo = clean_vendor_name(middle)

                if not (date and amount):
                    continue

                fingerprint = f"{date}|{memo.lower()}|{amount:.2f}|{source_account}"
                if fingerprint in seen_fingerprints:
                    continue
                seen_fingerprints.add(fingerprint)

                if any(kw in memo.lower() for kw in ["thank you", "payment"]):
                    amount = -abs(amount)

                transactions.append({
                    "date": date,
                    "memo": memo,
                    "account": "7090 - Uncategorized Expense",
                    "source": source_account,
                    "amount": amount
                })

    return {"transactions": transactions}
