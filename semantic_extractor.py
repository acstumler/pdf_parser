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
        if "closing" in line.lower() and "date" in line.lower():
            print(f"[DEBUG] Scanning for closing date in: {line}")
            match = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", line)
            if match:
                try:
                    parsed = parser.parse(match.group(1)).date()
                    print(f"[INFO] Closing date parsed successfully: {parsed}")
                    return parsed
                except Exception as e:
                    print(f"[ERROR] Failed to parse closing date from line: '{line}' → {e}")
    print("[WARNING] No matching line found for closing date")
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

def parse_transaction_block(block, source_account, start_date, end_date, seen_fingerprints):
    if not block or len(block) < 2:
        return None

    date_obj = extract_date_from_block(block)
    if not date_obj or not (start_date <= date_obj <= end_date):
        return None
    date_str = date_obj.strftime("%m/%d/%Y")

    full_block = " ".join(block)
    amount_match = re.search(r"-?\$?\d{1,3}(?:,\d{3})*\.\d{2}", full_block)
    if not amount_match:
        return None

    try:
        cleaned = amount_match.group().replace("$", "").replace(",", "")
        amount = float(cleaned)
    except:
        return None

    # Stronger memo filtering logic
    memo_candidates = [
        line.strip()
        for line in block[1:]
        if re.search(r"[A-Za-z]{3,}", line)  # must have at least 3 letters
        and not re.search(r"^\d{3}[-\s]?\d{3}[-\s]?\d{4}$", line)  # phone number
        and "detail continued" not in line.lower()
        and "pay over time" not in line.lower()
        and "cash advance" not in line.lower()
        and "continued on next page" not in line.lower()
    ]

    memo_line = max(memo_candidates, key=len) if memo_candidates else ""

    if not memo_line:
        print(f"[SKIPPED] Memo invalid: {block}")
        return None

    if "payment" in memo_line.lower() or "thank you" in memo_line.lower():
        amount = -abs(amount)

    # De-dupe transactions using fingerprint
    fingerprint = f"{date_str}|{memo_line.strip().lower()}|{amount:.2f}|{source_account}"
    if fingerprint in seen_fingerprints:
        print(f"[SKIPPED] Duplicate transaction: {fingerprint}")
        return None
    seen_fingerprints.add(fingerprint)

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

    seen_fingerprints = set()
    transactions = []

    for block in blocks:
        tx = parse_transaction_block(block, source_account, start_date, closing_date, seen_fingerprints)
        if tx:
            transactions.append(tx)

    print(f"[INFO] Final parsed transactions: {len(transactions)}")
    return {"transactions": transactions}
