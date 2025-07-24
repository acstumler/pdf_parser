import re
import pytesseract
from datetime import datetime, timedelta
from pdf2image import convert_from_path
import pdfplumber
from dateutil import parser as date_parser
from clean_vendor_name import clean_vendor_name

def extract_closing_date(text):
    match = re.search(r"(?:Closing Date|Closing Balance Date|Statement Date|Closing\s+Date)[^\d]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", text, re.IGNORECASE)
    if match:
        try:
            return datetime.strptime(match.group(1), "%m/%d/%Y")
        except ValueError:
            try:
                return datetime.strptime(match.group(1), "%m/%d/%y")
            except ValueError:
                pass
    # fallback: latest detected date in text
    all_dates = re.findall(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text)
    parsed_dates = []
    for d in all_dates:
        try:
            parsed_dates.append(date_parser.parse(d))
        except:
            continue
    return max(parsed_dates) if parsed_dates else datetime.today()

def ocr_text_from_pdf(pdf_path):
    images = convert_from_path(pdf_path)
    ocr_text = ""
    for img in images:
        text = pytesseract.image_to_string(img)
        ocr_text += text + "\n"
    return ocr_text

def extract_transactions(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text_blocks = []
        for page in pdf.pages:
            raw = page.extract_text()
            if raw:
                text_blocks.append(raw)

    text_content = "\n".join(text_blocks)
    ocr_content = ocr_text_from_pdf(pdf_path)

    combined_lines = list(set((text_content + "\n" + ocr_content).splitlines()))

    closing_date = extract_closing_date("\n".join(combined_lines))
    start_date = closing_date - timedelta(days=60)

    transactions = []

    for line in combined_lines:
        line = line.strip()

        match = re.match(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+\$?(-?\(?[\d,]+\.\d{2}\)?)", line)
        if not match:
            continue

        raw_date, raw_memo, raw_amount = match.groups()

        try:
            txn_date = date_parser.parse(raw_date)
            if not (start_date <= txn_date <= closing_date):
                continue
            formatted_date = txn_date.strftime("%m/%d/%y")
        except Exception:
            continue

        try:
            cleaned_amount = raw_amount.replace(",", "").replace("(", "-").replace(")", "")
            amount = round(float(cleaned_amount), 2)
        except ValueError:
            continue

        memo = clean_vendor_name(raw_memo)

        # Static placeholder for now (no AI or keyword classification)
        account = "Uncategorized – Expense"
        source = "UNKNOWN"

        transaction = {
            "date": formatted_date,
            "memo": memo,
            "account": account,
            "source": source,
            "amount": f"${abs(amount):,.2f}" if amount >= 0 else f"(${abs(amount):,.2f})"
        }

        transactions.append(transaction)

    return transactions
