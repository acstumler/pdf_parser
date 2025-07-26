import re
import fitz  # PyMuPDF
import pdfplumber
from io import BytesIO
from datetime import datetime, timedelta
from utils.clean_vendor_name import clean_vendor_name

# OCR support
import pytesseract
from pdf2image import convert_from_bytes

def extract_statement_period(text):
    patterns = [
        r"Closing Date[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})",
        r"Period Ending[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})",
        r"Statement Closing Date[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})",
        r"Closing Date[:\s]+([A-Za-z]{3,9} \d{1,2}, \d{4})"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            for fmt in ("%m/%d/%y", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y"):
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
    return None

def extract_account_source(text):
    match = re.search(r"Account Ending\s+(\d{1,6})", text)
    if match:
        return f"AMEX {match.group(1)}"
    return "Unknown"

def extract_transactions_from_text(text, source, closing_date):
    lines = text.split("\n")
    transactions = []
    seen = set()
    start_date = closing_date - timedelta(days=90)

    # Enhanced regex to tolerate real-world messiness
    transaction_regex = re.compile(
        r"(\d{1,2}/\d{1,2}/\d{2,4}).{0,50}?(-?\$?\(?\d{1,3}(?:,\d{3})*(?:\.\d{2})?\)?)",
        re.IGNORECASE
    )

    for line in lines:
        match = transaction_regex.search(line)
        if match:
            try:
                raw_date = match.group(1)
                date_obj = datetime.strptime(raw_date, "%m/%d/%y") if len(raw_date.split('/')[-1]) == 2 else datetime.strptime(raw_date, "%m/%d/%Y")
                if not (start_date <= date_obj <= closing_date):
                    continue

                date = date_obj.strftime("%m/%d/%Y")

                # Clean amount string
                raw_amount = match.group(2).replace("(", "-").replace(")", "").replace("$", "").replace(",", "")
                amount = float(raw_amount)

                memo = re.sub(r"\s+", " ", line).strip()
                if memo in seen:
                    continue
                seen.add(memo)
                vendor = clean_vendor_name(memo)

                transactions.append({
                    "date": date,
                    "memo": vendor,
                    "account": "Unknown",
                    "source": source,
                    "amount": f"${amount:,.2f}"
                })
            except Exception as e:
                print("Error parsing line:", line, "| Error:", e)
                continue
        else:
            print("Rejected line (no match):", line)

    return transactions

def extract_text_from_pdf(pdf_bytes):
    text = ""

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        pass

    if not text.strip():
        try:
            text = "\n".join([page.get_text() for page in fitz.open(stream=pdf_bytes, filetype="pdf")])
        except Exception:
            pass

    if not text.strip():
        try:
            images = convert_from_bytes(pdf_bytes)
            text = "\n".join(pytesseract.image_to_string(img) for img in images)
        except Exception:
            pass

    return text

def extract_transactions(pdf_bytes: bytes):
    full_text = extract_text_from_pdf(pdf_bytes)

    print("\n======= EXTRACTED TEXT START =======\n")
    print(full_text[:5000])
    print("\n======== EXTRACTED TEXT END ========\n")

    closing_date = extract_statement_period(full_text)
    if not closing_date:
        raise ValueError("Unable to extract closing date")

    source = extract_account_source(full_text)

    transactions = extract_transactions_from_text(full_text, source, closing_date)
    return transactions
