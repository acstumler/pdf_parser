import re
import fitz  # PyMuPDF
import pdfplumber
from datetime import datetime, timedelta
from utils.clean_vendor_name import clean_vendor_name


def extract_statement_period(text):
    """
    Extracts the closing date from the PDF header using MM/DD/YY format.
    """
    match = re.search(r"Closing Date\s+(\d{1,2}/\d{1,2}/\d{2})", text)
    if match:
        try:
            closing_date = datetime.strptime(match.group(1), "%m/%d/%y")
            return closing_date
        except ValueError:
            pass
    return None


def extract_account_source(text):
    """
    Extracts account source (e.g. AMEX 61005) from statement header.
    """
    match = re.search(r"Account Ending\s+(\d{1,6})", text)
    if match:
        return f"AMEX {match.group(1)}"
    return "Unknown"


def extract_transactions_from_text(text, source, closing_date):
    lines = text.split("\n")
    transactions = []
    seen = set()
    start_date = closing_date - timedelta(days=90)

    for line in lines:
        match = re.search(r"(\d{1,2}/\d{1,2}/\d{2}).*?\$?(-?\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", line)
        if match:
            try:
                raw_date = match.group(1)
                date_obj = datetime.strptime(raw_date, "%m/%d/%y")
                if not (start_date <= date_obj <= closing_date):
                    continue
                date = date_obj.strftime("%m/%d/%Y")
                amount = float(match.group(2).replace(",", ""))
                memo = re.sub(r"\s+", " ", line).strip()
                if len(memo) < 20 or memo in seen:
                    continue
                seen.add(memo)
                vendor = clean_vendor_name(memo)
                transactions.append({
                    "date": date,
                    "memo": vendor,
                    "account": "Unknown",  # classification skipped
                    "source": source,
                    "amount": f"${amount:,.2f}"
                })
            except Exception:
                continue
    return transactions


def extract_transactions(pdf_path: str):
    with pdfplumber.open(pdf_path) as pdf:
        raw_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    closing_date = extract_statement_period(raw_text)
    if not closing_date:
        raise ValueError("Unable to extract closing date")

    source = extract_account_source(raw_text)

    # OCR fallback
    ocr_text = ""
    try:
        for page in fitz.open(pdf_path):
            ocr_text += page.get_text()
    except Exception:
        pass

    combined_text = raw_text + "\n" + ocr_text
    transactions = extract_transactions_from_text(combined_text, source, closing_date)
    return transactions
