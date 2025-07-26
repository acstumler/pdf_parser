import re
from datetime import datetime
from .raw_parser import extract_text_blocks
from .utils.memo_cleaner import clean_memo_text
from .utils.date_utils import is_within_date_range
from .utils.ocr_utils import extract_text_with_ocr


def extract_transactions(text: str, learned_memory: dict = {}):
    print("📄 Beginning structured extraction process")
    transactions = []

    # Try OCR fallback if text appears too empty or malformed
    if len(text.strip().splitlines()) < 10 or "STATEMENT" not in text.upper():
        print("⚠️ Low confidence in extracted text — attempting OCR fallback")
        text = extract_text_with_ocr(text)

    lines = text.splitlines()
    lines = [line.strip() for line in lines if line.strip()]
    print(f"🧾 Scanning {len(lines)} lines from input...")

    # Extract header info (statement date range and source)
    statement_source = "Unknown"
    closing_date = None

    for line in lines:
        if match := re.search(r"Account Ending(?:\D*?)(\d{5})", line):
            statement_source = f"AMEX {match.group(1)}"
        if match := re.search(r"Closing Date[:\s]*([A-Za-z]{3,9} \d{1,2},? \d{4})", line):
            try:
                closing_date = datetime.strptime(match.group(1).replace(",", ""), "%B %d %Y")
                print(f"🗓️ Parsed closing date: {closing_date.strftime('%m/%d/%Y')}")
            except Exception as e:
                print(f"⚠️ Failed to parse closing date: {e}")

    transaction_block_pattern = re.compile(
        r"(?P<date>\d{2}/\d{2}/\d{2,4})\*?\s+(?P<description>.+?)\s+\$?(?P<amount>[-]?\(?\$?\d+[\.,]?\d{0,2}\)?)"
    )

    for line in lines:
        print(f"🔍 SCANNING LINE: {line}")
        match = transaction_block_pattern.search(line)
        if not match:
            print(f"❌ REJECTED LINE (NO MATCH): {line}")
            continue

        date_str = match.group("date")
        try:
            parsed_date = datetime.strptime(date_str, "%m/%d/%Y")
        except ValueError:
            try:
                parsed_date = datetime.strptime(date_str, "%m/%d/%y")
            except ValueError:
                print(f"❌ Invalid date: {date_str}")
                continue

        if closing_date and not is_within_date_range(parsed_date, closing_date):
            print(f"❌ Outside closing window: {parsed_date.strftime('%m/%d/%Y')}")
            continue

        raw_memo = match.group("description")
        cleaned_memo = clean_memo_text(raw_memo)

        raw_amount = match.group("amount")
        formatted_amount = (
            f"-${raw_amount.strip('()$')}" if "(" in raw_amount or "-" in raw_amount else f"${raw_amount.strip('$')}"
        )

        transaction = {
            "date": parsed_date.strftime("%m/%d/%Y"),
            "memo": cleaned_memo,
            "account": "Unknown",
            "source": statement_source,
            "amount": formatted_amount,
        }

        print(f"✅ MATCHED TRANSACTION: {transaction}")
        transactions.append(transaction)

    print(f"📊 Parsed {len(transactions)} transactions.")
    return transactions
