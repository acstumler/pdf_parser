import re
from dateutil import parser
from datetime import datetime
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
            except:
                continue
    return None

def build_candidate_blocks(text_lines):
    blocks = []
    current_block = []
    for line in text_lines:
        line = line.strip()
        if not line:
            continue

        if re.search(r"\d{2}/\d{2}/\d{2,4}", line):
            if current_block:
                blocks.append(current_block)
            current_block = [line]
        elif current_block:
            current_block.append(line)
    if current_block:
        blocks.append(current_block)
    return blocks

def extract_transactions(text_lines, learned_memory=None):
    if learned_memory is None:
        learned_memory = {}

    source_account = extract_source_account(text_lines)
    closing_date = extract_closing_date(text_lines)
    if not closing_date:
        return {"transactions": []}

    blocks = build_candidate_blocks(text_lines)

    # Use earliest valid block as start
    valid_dates = []
    for block in blocks:
        date = extract_date_from_block(block)
        if date and date <= closing_date:
            valid_dates.append(date)

    if not valid_dates:
        return {"transactions": []}

    start_date = min(valid_dates)

    transactions = []
    for block in blocks:
        tx = parse_transaction_block(block, source_account, start_date, closing_date)
        if tx:
            transactions.append(tx)

    return {"transactions": transactions}

def extract_date_from_block(block):
    if not block:
        return None
    date_match = re.search(r"\d{2}/\d{2}/\d{2,4}", block[0])
    if not date_match:
        return None
    try:
        return parser.parse(date_match.group(0)).date()
    except:
        return None

def is_structurally_valid_block(block):
    if not block or len(block) < 2:
        return False

    # Must include at least one line with alphabetic vendor-like content
    has_vendor_line = any(re.search(r"[A-Za-z]{3,}", line) for line in block)
    if not has_vendor_line:
        return False

    # Must include a dollar amount or valid numeric format
    has_amount = any(re.search(r"\$?[\d,]+\.\d{2}", line) for line in block)
    if not has_amount:
        return False

    # Exclude blocks where every line is just a number or dollar amount
    all_numeric = all(re.fullmatch(r"[\$,.\d\s\-]+", line) for line in block)
    if all_numeric:
        return False

    return True

def parse_transaction_block(block, source_account, start_date, end_date):
    if not is_structurally_valid_block(block):
        return None

    date_obj = extract_date_from_block(block)
    if not date_obj or not (start_date <= date_obj <= end_date):
        return None
    date_str = date_obj.strftime("%m/%d/%Y")

    # Extract amount
    full_block = " ".join(block)
    amount_match = re.findall(r"\$?\s?[\d,]+\.\d{2}", full_block)
    if not amount_match:
        return None

    try:
        amount = float(amount_match[-1].replace("$", "").replace(",", "").strip())
    except:
        return None

    memo_line = next((line for line in block if re.search(r"[A-Za-z]", line)), "").strip()
    if not memo_line or memo_line.lower().startswith("closing date"):
        return None

    memo = memo_line.split("  ")[0]
    if "payment" in memo.lower():
        amount = -abs(amount)

    return {
        "date": date_str,
        "memo": memo,
        "amount": amount,
        "source": source_account
    }
