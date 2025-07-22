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

    # Use earliest valid transaction block as period start
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

def parse_transaction_block(block, source_account, start_date, end_date):
    if not block:
        return None

    date_obj = extract_date_from_block(block)
    if not date_obj or not (start_date <= date_obj <= end_date):
        return None
    date_str = date_obj.strftime("%m/%d/%Y")

    full_block = " ".join(block)

    # Allow "interest" memos but exclude interest rate disclosures
    skip_if_patterns = [
        r"\d{1,2}\.\d{1,2}%",          # percentages like 24.24%
        r"annual percentage rate",     # APR disclosures
        r"\(v\)",                      # variable rate marker
        r"trailing interest",          # keyword for summary info
        r"interest rate",              # not interest charges
    ]
    for pattern in skip_if_patterns:
        if re.search(pattern, full_block, re.IGNORECASE):
            return None

    amount_match = re.findall(r"\$?\s?[\d,]+\.\d{2}", full_block)
    if not amount_match:
        return None

    try:
        amount = float(amount_match[-1].replace("$", "").replace(",", "").strip())
    except:
        return None

    memo_line = next((line for line in block if re.search(r"[A-Za-z]", line)), "").strip()
    if not memo_line:
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
