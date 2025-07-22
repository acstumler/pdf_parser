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

def extract_statement_period(text_lines) -> tuple[Optional[datetime], Optional[datetime]]:
    # Look for two dates like "11/28/2023 – 12/28/2023"
    for line in text_lines:
        line = line.replace("–", "-")  # Normalize dashes
        date_matches = re.findall(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", line)
        if len(date_matches) == 2:
            try:
                start = parser.parse(date_matches[0]).date()
                end = parser.parse(date_matches[1]).date()
                return start, end
            except Exception:
                continue

        # Example: "Oct 28 - Nov 27, 2023"
        range_match = re.search(r"([A-Za-z]{3,9} \d{1,2})\s*[-to]+\s*([A-Za-z]{3,9} \d{1,2}, \d{4})", line)
        if range_match:
            try:
                start = parser.parse(range_match.group(1)).date()
                end = parser.parse(range_match.group(2)).date()
                return start, end
            except Exception:
                continue

    return None, None

def extract_transactions(text_lines, learned_memory=None):
    if learned_memory is None:
        learned_memory = {}

    transactions = []
    current_block = []
    source_account = extract_source_account(text_lines)
    start_date, end_date = extract_statement_period(text_lines)

    # If we can't extract both dates, abort the parse
    if not start_date or not end_date:
        return {"transactions": []}

    for line in text_lines:
        line = line.strip()
        if not line:
            continue

        if re.search(r"\d{2}/\d{2}/\d{2,4}", line):
            if current_block:
                tx = parse_transaction_block(current_block, source_account, start_date, end_date)
                if tx:
                    transactions.append(tx)
            current_block = [line]
        elif current_block:
            current_block.append(line)

    if current_block:
        tx = parse_transaction_block(current_block, source_account, start_date, end_date)
        if tx:
            transactions.append(tx)

    return {"transactions": transactions}

def parse_transaction_block(block, source_account, start_date, end_date):
    if not block:
        return None

    # Search for date in any position in the first line
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

    return {
        "date": date_str,
        "memo": memo,
        "amount": amount,
        "source": source_account
    }
