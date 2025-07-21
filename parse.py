# parse.py

import io
import uuid
import pdfplumber
import re
from datetime import datetime
import pytesseract
from PIL import Image

# Patterns
DATE_REGEX = re.compile(r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b')
AMOUNT_REGEX = re.compile(r'-?\$?\d{1,3}(,\d{3})*(\.\d{2})')
SOURCE_REGEX = re.compile(r'Account Ending(?: in)?\s+(\d{4,6})', re.IGNORECASE)

def clean_amount(value):
    value = value.replace('$', '').replace(',', '').replace('(', '-').replace(')', '')
    try:
        return float(value)
    except ValueError:
        return None

def classify_transaction_type(memo):
    memo_lower = memo.lower()
    if "interest" in memo_lower:
        return "interest", "7100 - Interest Expense"
    if "fee" in memo_lower:
        return "fee", "7110 - Loan Fees"
    if "payment" in memo_lower or "thank you" in memo_lower:
        return "payment", "Credit Card Payment"
    if "credit" in memo_lower or "refund" in memo_lower:
        return "credit", "4090 - Refunds and Discounts (Contra-Revenue)"
    return "charge", ""

def is_valid_amount(amount):
    return amount is not None and abs(amount) >= 0.01

def extract_transactions(pdf_bytes):
    transactions = []
    current_source = None

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()

            # Fallback to OCR if page is image-based
            if not text or len(text.strip()) < 30:
                print(f"[OCR] Extracting text from image on page {page_num + 1}")
                image = page.to_image(resolution=300).original
                text = pytesseract.image_to_string(image)

            lines = text.split('\n')

            for line in lines:
                if not current_source:
                    src_match = SOURCE_REGEX.search(line)
                    if src_match:
                        current_source = f"American Express {src_match.group(1)}"

            i = 0
            while i < len(lines):
                line = lines[i].strip()
                date_match = DATE_REGEX.search(line)

                if date_match:
                    raw_date = date_match.group(1).replace('-', '/').replace('.', '/')
                    try:
                        parsed_date = datetime.strptime(raw_date, "%m/%d/%Y").strftime("%m/%d/%Y")
                    except ValueError:
                        try:
                            parsed_date = datetime.strptime(raw_date, "%m/%d/%y").strftime("%m/%d/%Y")
                        except ValueError:
                            i += 1
                            continue

                    memo_lines = [line]
                    amount = None

                    # Look up to 6 lines ahead for amount
                    for j in range(1, 6):
                        if i + j < len(lines):
                            next_line = lines[i + j].strip()
                            amt_match = AMOUNT_REGEX.search(next_line)
                            if amt_match:
                                amount_val = clean_amount(amt_match.group(0))
                                if is_valid_amount(amount_val):
                                    amount = amount_val
                                    i = i + j
                                    break
                            else:
                                memo_lines.append(next_line)

                    full_text = ' '.join(memo_lines)
                    memo_clean = re.sub(DATE_REGEX, '', full_text)
                    memo_clean = re.sub(AMOUNT_REGEX, '', memo_clean)
                    memo_clean = re.sub(r'\s+', ' ', memo_clean).strip()

                    txn_type, pre_classification = classify_transaction_type(memo_clean)

                    if is_valid_amount(amount):
                        transactions.append({
                            "id": str(uuid.uuid4()),
                            "date": parsed_date,
                            "memo": memo_clean,
                            "amount": amount,
                            "type": txn_type,
                            "section": "",
                            "uploadedFrom": current_source or "",  # ✅ FIXED: Show AMEX 61005
                            "uploadedAt": None,
                            "account": pre_classification,
                            "classificationSource": "default" if not pre_classification else "preclassified"
                        })

                i += 1

    print(f"✅ Parsed {len(transactions)} total financial entries.")
    return { "transactions": transactions }
