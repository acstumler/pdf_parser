import re

def extract_visual_rows_v2(file_path):
    with open(file_path, "rb") as f:
        text = f.read().decode(errors="ignore")

    lines = text.splitlines()
    transactions = []
    current_block = []

    for line in lines:
        if is_transaction_start(line):
            if current_block:
                tx = parse_block(current_block)
                if tx:
                    transactions.append(tx)
                current_block = []
        current_block.append(line)

    if current_block:
        tx = parse_block(current_block)
        if tx:
            transactions.append(tx)

    return transactions

def is_transaction_start(line):
    return bool(re.match(r"\d{2}/\d{2}/\d{2,4}", line.strip()))

def parse_block(block):
    full_text = " ".join(block).strip()
    date_match = re.search(r"(\d{2}/\d{2}/\d{2,4})", full_text)
    amount_match = re.search(r"\$?(-?\(?\d{1,4}(?:,\d{3})*(?:\.\d{2})\)?)", full_text)

    if not date_match or not amount_match:
        return None

    raw_date = date_match.group(1)
    raw_amount = amount_match.group(1)

    clean_amount = raw_amount.replace("(", "-").replace(")", "").replace("$", "").replace(",", "")
    try:
        amount = round(float(clean_amount), 2)
    except ValueError:
        return None

    # Remove the date and amount from the full text to isolate memo
    memo_text = full_text.replace(raw_date, "").replace(raw_amount, "").strip()
    memo_text = re.sub(r"[\s]{2,}", " ", memo_text)
    memo = memo_text[:80].strip() or "Unknown"

    return {
        "date": raw_date,
        "memo": memo,
        "amount": amount,
        "source": "AMEX 61005"
    }
