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
            except:
                continue
    return None

def build_candidate_blocks(text_lines):
    blocks = []
    current_block = []
    previous_y = None

    for line in text_lines:
        if isinstance(line, dict):
            text, y0 = line.get("text", "").strip(), line.get("top", None)
        else:
            text, y0 = line.strip(), None

        if not text:
            continue

        if re.match(r"\d{2}/\d{2}/\d{2,4}", text):
            if current_block:
                blocks.append(current_block)
            current_block = [text]
            previous_y = y0
        elif current_block:
            if y0 and previous_y and abs(y0 - previous_y) > 15:
                continue
            current_block.append(text)
            previous_y = y0

    if current_block:
        blocks.append(current_block)
    return blocks

def extract_statement_summary_totals(text_lines):
    summary = {"payments": 0.0, "charges": 0.0, "interest": 0.0}
    for line in text_lines:
        lower = line.lower()
        if "payments" in lower or "credits" in lower:
            match = re.search(r"-?\$[\d,]+\.\d{2}", line)
            if match:
                summary["payments"] = float(match.group().replace("$", "").replace(",", "").replace("-", "").strip())
        elif "new charges" in lower:
            match = re.search(r"\$[\d,]+\.\d{2}", line)
            if match:
                summary["charges"] = float(match.group().replace("$", "").replace(",", ""))
        elif "interest charged" in lower:
            match = re.search(r"\$[\d,]+\.\d{2}", line)
            if match:
                summary["interest"] = float(match.group().replace("$", "").replace(",", ""))
    return summary

def verify_totals(transactions, extracted_totals):
    parsed_payments = sum(t["amount"] for t in transactions if t["amount"] < 0)
    parsed_charges = sum(t["amount"] for t in transactions if t["amount"] > 0)
    return abs(abs(parsed_payments) - extracted_totals["payments"]) < 10 and \
           abs(parsed_charges - extracted_totals["charges"]) < 10

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
    has_vendor_line = any(re.search(r"[A-Za-z]{3,}", line) for line in block)
    if not has_vendor_line:
        return False
    has_amount = any(re.search(r"\$?[\d,]+\.\d{2}", line) for line in block)
    if not has_amount:
        return False
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

    full_block = " ".join(block)
    amount_match = re.findall(r"\$?\s?[\d,]+\.\d{2}", full_block)
    if not amount_match:
        return None

    try:
        amount = float(amount_match[-1].replace("$", "").replace(",", "").strip())
    except:
        return None

    memo_line = next((line for line in block if re.search(r"[A-Za-z]", line)), "").strip()
    if not memo_line or len(memo_line.strip()) <= 2:
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

def extract_transactions(text_lines, learned_memory=None):
    if learned_memory is None:
        learned_memory = {}

    source_account = extract_source_account(text_lines)
    closing_date = extract_closing_date(text_lines)
    if not closing_date:
        return {"transactions": []}

    start_date = closing_date - timedelta(days=45)

    blocks = build_candidate_blocks(text_lines)

    transactions = []
    for block in blocks:
        tx = parse_transaction_block(block, source_account, start_date, closing_date)
        if tx:
            transactions.append(tx)

    extracted_totals = extract_statement_summary_totals(text_lines)
    verify_totals(transactions, extracted_totals)

    return {"transactions": transactions}
