import re
from datetime import datetime
from pdfminer.high_level import extract_text
from pdf2image import convert_from_path
import pytesseract
from io import BytesIO
from PIL import Image

def extract_text_from_pdf(path):
    try:
        text = extract_text(path)
        if text and len(text.strip()) > 50:
            return text
        else:
            return extract_text_via_ocr(path)
    except Exception:
        return extract_text_via_ocr(path)

def extract_text_via_ocr(path):
    images = convert_from_path(path)
    full_text = ""
    for img in images:
        buffered = BytesIO()
        img.save(buffered, format="JPEG")
        text = pytesseract.image_to_string(Image.open(buffered))
        full_text += text + "\n"
    return full_text

def extract_statement_period(text):
    # Looks for date ranges like "Oct 28 – Nov 27, 2023" or similar
    date_range_pattern = re.compile(r'([A-Za-z]{3,9})[\s\-–]+(\d{1,2})[\s\-–]+[–\-—][\s\-–]+([A-Za-z]{3,9})[\s\-–]+(\d{1,2}),\s*(\d{4})')
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
    match = re.search(r'Account Ending[\s\-]*?(\d{5})', text, re.IGNORECASE)
    if match:
        return f"AMEX {match.group(1)}"
    return "Unknown"

def extract_transactions(text, start_date=None, end_date=None, source="Unknown"):
    transaction_pattern = re.compile(
        r'(\d{2}/\d{2}/\d{2,4})\s+([^\n]*?)\s+\$?(-?\(?\d{1,4}(?:,\d{3})*(?:\.\d{2})?\)?)',
        re.MULTILINE
    )
    matches = transaction_pattern.findall(text)
    transactions = []

    for match in matches:
        raw_date, raw_memo, raw_amount = match

        try:
            date_obj = datetime.strptime(raw_date, "%m/%d/%Y")
        except ValueError:
            try:
                date_obj = datetime.strptime(raw_date, "%m/%d/%y")
            except:
                continue

        if start_date and end_date:
            if not (start_date <= date_obj <= end_date):
                continue

        amount_clean = raw_amount.replace(',', '').replace('(', '-').replace(')', '')
        try:
            amount_float = float(amount_clean)
        except:
            continue

        amount_formatted = f"${abs(amount_float):,.2f}"
        if amount_float < 0:
            amount_formatted = f"(${abs(amount_float):,.2f})"

        memo_cleaned = clean_memo(raw_memo)

        transactions.append({
            "date": date_obj.strftime("%m/%d/%Y"),
            "memo": memo_cleaned,
            "account": "Unknown",
            "source": source,
            "amount": amount_formatted
        })

    return transactions

def clean_memo(memo):
    memo = memo.strip()
    memo = re.sub(r'\*+', '', memo)
    memo = re.sub(r'\d{4,}', '', memo)  # Remove long numeric codes
    memo = re.sub(r'[^\w\s&.,/-]', '', memo)
    words = memo.split()
    filtered = [w for w in words if w.lower() not in ("aplpay", "tst", "store", "inc", "llc", "co")]
    return " ".join(filtered).title()

def parse_pdf(path):
    text = extract_text_from_pdf(path)
    start_date, end_date = extract_statement_period(text)
    source = extract_source_account(text)
    transactions = extract_transactions(text, start_date, end_date, source)
    return transactions
