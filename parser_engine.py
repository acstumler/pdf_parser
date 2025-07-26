import re
import pdfplumber
from io import BytesIO
from datetime import datetime, timedelta
from utils.clean_vendor_name import clean_vendor_name

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

    transaction_regex = re.compile(
        r"(\d{1,2}/\d{1,2}/\d{2,4}).{0,100}?(-?\$?\(?\d{1,3}(?:,\d{3})*(?:\.\d{2})?\)?)",
        re.IGNORECASE
    )

    for line in lines:
        line = line.strip()
        print("🔍 SCANNING LINE:", line)
        if not line:
            continue

        try:
            match = transaction_regex.search(line)
            if match:
                raw_date = match.group(1)
                date_obj = datetime.strptime(raw_date, "%m/%d/%y") if len(raw_date.split('/')[-1]) == 2 else datetime.strptime(raw_date, "%m/%d/%Y")
                if not (start_date <= date_obj <= closing_date):
                    continue

                date = date_obj.strftime("%m/%d/%Y")

                raw_amount = match.group(2).replace("(", "-").replace(")", "").replace("$", "").replace(",", "")
                amount = float(raw_amount)

                memo = re.sub(r"\s+", " ", line).strip()
                if memo in seen:
                    continue
                seen.add(memo)
                vendor = clean_vendor_name(memo)

                transaction = {
                    "date": date,
                    "memo": vendor,
                    "account": "Unknown",
                    "source": source,
                    "amount": f"${amount:,.2f}"
                }

                print("✅ MATCHED TRANSACTION:", transaction)
                transactions.append(transaction)
            else:
                print("❌ REJECTED LINE (NO MATCH):", line)

        except Exception as e:
            import traceback
            print("❌ ERROR while parsing line:", line)
            traceback.print_exc()

    return transactions

def extract_text_from_pdf(pdf_bytes):
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as e:
        print("❌ Failed to extract text via pdfplumber:", e)
        return ""

def extract_transactions(pdf_bytes: bytes):
    full_text = extract_text_from_pdf(pdf_bytes)

    print("\n======= EXTRACTED TEXT START =======\n")
    print(full_text[:5000])
    print("\n======== EXTRACTED TEXT END ========\n")

    closing_date = extract_statement_period(full_text)
    if not closing_date:
        raise ValueError("Unable to extract closing date")

    source = extract_account_source(full_text)
    return extract_transactions_from_text(full_text, source, closing_date)
