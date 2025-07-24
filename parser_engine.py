import re
import logging
from datetime import datetime, timedelta
from clean_vendor_name import clean_vendor_name

logger = logging.getLogger(__name__)

DATE_REGEX = re.compile(r"\d{2}/\d{2}/\d{2}")
AMOUNT_REGEX = re.compile(r"\(?-?\$?\d{1,3}(,\d{3})*(\.\d{2})?\)?")

def is_valid_date(text):
    try:
        datetime.strptime(text.strip(), "%m/%d/%y")
        return True
    except Exception:
        return False

def is_valid_amount(text):
    return bool(AMOUNT_REGEX.search(text.strip()))

def parse_amount(text):
    raw = re.sub(r"[^\d.\-()]", "", text)
    if "(" in raw and ")" in raw:
        return -float(raw.replace("(", "").replace(")", ""))
    return float(raw)

def clean_memo(text):
    return re.sub(r"[^\w\s&\-\'/,.*@#]", "", text).strip()

def extract_transactions_from_text(text, learned_memory={}):
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    logger.info(f"[INFO] Total combined lines: {len(lines)}")

    blocks = build_candidate_blocks(lines)
    logger.info(f"[INFO] Found {len(blocks)} candidate blocks")

    parsed_transactions = []
    seen_memos = set()
    today = datetime.today()
    min_date = today - timedelta(days=60)

    for block in blocks:
        if len(block) != 3:
            continue

        date_raw, memo_raw, amount_raw = block
        if not (is_valid_date(date_raw) and is_valid_amount(amount_raw)):
            continue

        try:
            tx_date = datetime.strptime(date_raw, "%m/%d/%y")
            if tx_date < min_date or tx_date > today:
                logger.info(f"[SKIP] Date out of range: {tx_date.strftime('%Y-%m-%d')}")
                continue

            memo = clean_memo(memo_raw)
            amount = parse_amount(amount_raw)
            unique_id = f"{tx_date.isoformat()}_{memo}_{amount}"
            if unique_id in seen_memos:
                continue

            seen_memos.add(unique_id)

            source = extract_account_source(text)
            parsed_transactions.append({
                "date": tx_date.strftime("%Y-%m-%d"),
                "memo": memo,
                "amount": amount,
                "source": source
            })

        except Exception as e:
            logger.warning(f"[SKIP] Failed to parse block: {block} → {e}")

    logger.info(f"[INFO] Final parsed transactions: {len(parsed_transactions)}")
    return parsed_transactions

def build_candidate_blocks(lines):
    blocks = []
    i = 0
    while i <= len(lines) - 3:
        line1, line2, line3 = lines[i].strip(), lines[i + 1].strip(), lines[i + 2].strip()
        if is_valid_date(line1) and is_valid_amount(line3):
            blocks.append([line1, line2, line3])
            i += 3
        else:
            i += 1
    return blocks

def extract_account_source(text):
    match = re.search(r"(AMEX|CHASE|BANK|CAPITAL ONE|WELLS FARGO).*?(\d{4,6})", text, re.IGNORECASE)
    if match:
        return f"{match.group(1).upper()} {match.group(2)}"
    return "Unknown"
