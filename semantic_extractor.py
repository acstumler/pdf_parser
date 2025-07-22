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

def extract_first_transaction_date(text_lines) -> Optional[datetime]:
    for line in text_lines:
        date_match = re.search(r"\d{2}/\d{2}/\d{2,4}", line)
        if date_match:
            try:
                return parser.parse(date_match.group(0)).date()
            except:
                continue
    return None

def extract_transactions(text_lines, learned_memory=None):
    if learned_memory is None:
        learned_memory = {}

    transactions = []
    current_block = []
    source_account = extract_source_account(text_lines)
    closing_date = extract_closing_date(text_lines)
    first_tx_date = extract_first_transaction_date(text_lines)

    if not closing_date or not first_tx_date:
        return {"transactions": []}

    for line in text_lines:
        line = line.strip()
        if not line:
            continue

        if re.search(r"\d{2}/\d{2}/\d{2,4}", line):
            if current_block:
                tx = parse_transaction_block(current_block, source_account, first_tx_date, closing_date)
                if tx:
                    transactions.append(tx)
            current_block = [line]
        elif current_block:
            current_block.append(line)

    if current_block:
        tx = parse_transaction_block(current_block, source_account, first_tx_date, closing_date)
        if tx:
            transactions.append(tx)

    return {"transactions": transactions}

def parse_transaction_block(block, source_account, start_date, end_date):
    if not block:
        return None

    date_match = re.search(r"\d{2}/\d{2}/\d{2,4}", block[0])
    if not date_match:
        return None

    try:
        date_obj = parser.parse(date_match.group(0)).date()
        if not (start_date <= date_obj <= end_date):
            return None
        date_str = date_obj.strftime("%m/%d/%Y")
    except:
        return None

    full_block = " ".join(block)
    noise_keywords = ["payment due", "customer care", "www.", "american express", "carol stream", "visit"]
    if any(kw in full_block.lower() for kw in noise_keywords):
        return None

    amount_match = re.findall(r"\$?\s?[\d,]+\.\d{2}", full_block)
    if not amount_match:
        return None

    amount_str = amount_match[-1].replace("$", "").replace(",", "").strip()
    try:
        amount = float(amount_str)
    except:
        return None

    memo_line = next((line for line in block if re.search(r"[A-Za-z]", line)), "").strip()
    if not memo_line:
        return None

    memo = memo_line.split("  ")[0]

    # Payment reversal logic
    if "payment" in memo.lower():
        amount = -abs(amount)

    return {
        "date": date_str,
        "memo": memo,
        "amount": amount,
        "source": source_account
    }
