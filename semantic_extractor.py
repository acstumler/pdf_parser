import re
from dateutil import parser
from datetime import datetime, timedelta
from typing import Optional

def extract_source_account(text_lines):
    for line in text_lines:
        if "account ending" in line.lower():
            match = re.search(r"(account ending\s+)?(\d{4,6})", line, re.IGNORECASE)
            if match:
                return f"AMEX {match.group(2)}"
    return "Unknown"

def extract_closing_date(text_lines) -> Optional[datetime]:
    for line in text_lines:
        match = re.search(r"Closing Date (\d{1,2}/\d{1,2}/\d{2,4})", line, re.IGNORECASE)
        if match:
            try:
                return parser.parse(match.group(1)).date()
            except Exception as e:
                print(f"[ERROR] Failed to parse date from line '{line}': {e}")
    return None

def build_candidate_blocks(text_lines):
    blocks = []
    current_block = []

    for line in text_lines:
        if isinstance(line, dict):
            text = line.get("text", "").strip()
        else:
            text = line.strip()

        if not text:
            continue

        if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", text):
            if current_block:
                blocks.append(current_block)
            current_block = [text]
        elif current_block:
            current_block.append(text)

    if current_block:
        blocks.append(current_block)
    return blocks

def extract_date_from_block(block):
    if not block:
        return None
    date_match = re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", block[0])
    if not date_match:
        return None
    try:
        return parser.parse(date_match.group(0)).date()
    except:
        return None

def parse_transaction_block(block, source_account, start_date, end_date):
    if not block or len(block) < 2:
        return None

    date_obj = extract_date_from_block(block)
    if not date_obj or not (start_date <= date_obj <= end_date):
        return None
    date_str = date_obj.strftime("%m/%d/%Y")

    full_block = " ".join(block)
    amount_match = re.search(r"-?\$[\d,]+\.\d{2}", full_block)
    if not amount_match:
        return None

    try:
        amount = float(
            amount_match.group().replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
        )
    except:
        return None

    memo_line = next((line for line in block[1:] if re.search(r"[A-Za-z]{3,}", line)), "").strip()
    if not memo_line or len(memo_line) <= 2:
        return None

    if "payment" in memo_line.lower():
        amount = -abs(amount)

    return {
        "date": date_str,
        "memo": memo_line,
        "amount": amount,
        "source": source_account
    }

def extract_transactions(text_lines, learned_memory=None):
    if learned_memory is None:
        learned_memory = {}

    closing_date = extract_closing_date(text_lines)
    if not closing_date:
        print("[WARNING] No closing date found. Using fallback range.")
        closing_date = datetime.today().date()

    start_date = closing_date - timedelta(days=45)
    print(f"[INFO] Enforcing date filter: Start = {start_date}, End = {closing_date}")

    source_account = extract_source_account(text_lines)
    blocks = build_candidate_blocks(text_lines)
    print(f"[INFO] Found {len(blocks)} candidate blocks")

    transactions = []
    for block in blocks:
        tx = parse_transaction_block(block, source_account, start_date, closing_date)
        if tx:
            transactions.append(tx)

    print(f"[INFO] Parsed {len(transactions)} valid transactions")
    return {"transactions": transactions}
