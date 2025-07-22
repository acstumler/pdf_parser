import re
from dateutil import parser

def extract_source_account(text_lines):
    """
    Extracts the source account (e.g., AMEX 61005) from the header/footer of a document.
    """
    for line in text_lines:
        match = re.search(r'(account ending\s+)?(\d{4,6})', line, re.IGNORECASE)
        if match:
            return f"AMEX {match.group(2)}"
    return "Unknown"

def extract_transactions(text_lines, learned_memory=None):
    if learned_memory is None:
        learned_memory = {}

    transactions = []
    current_block = []
    source_account = extract_source_account(text_lines)

    for line in text_lines:
        line = line.strip()

        if not line:
            continue

        # Start a new block if a date line is detected
        if re.match(r"\d{2}/\d{2}/\d{2,4}", line.lstrip()):
            if current_block:
                transaction = parse_transaction_block(current_block, source_account)
                if transaction:
                    transactions.append(transaction)
            current_block = [line]
        elif current_block:
            current_block.append(line)

    if current_block:
        transaction = parse_transaction_block(current_block, source_account)
        if transaction:
            transactions.append(transaction)

    return {"transactions": transactions}


def parse_transaction_block(block, source_account):
    """
    Given a block of lines representing a transaction, extract the date, memo, and amount.
    """
    if not block:
        return None

    date_match = re.match(r"\d{2}/\d{2}/\d{2,4}", block[0].strip())
    if not date_match:
        return None

    try:
        date_obj = parser.parse(date_match.group(0))
        date_str = date_obj.strftime("%m/%d/%Y")
    except Exception:
        return None

    full_block = " ".join(block)

    # Find the amount (last matching dollar-like pattern)
    amount_match = re.findall(r"\$?\s?[\d,]+\.\d{2}", full_block)
    if not amount_match:
        return None

    amount_str = amount_match[-1].replace("$", "").replace(",", "").strip()
    try:
        amount = float(amount_str)
    except Exception:
        return None

    # Simplified memo: first line with letters (excluding numeric-only)
    memo_line = next((line for line in block if any(char.isalpha() for char in line)), "")
    memo = memo_line.strip().split("  ")[0]

    return {
        "date": date_str,
        "memo": memo,
        "amount": amount,
        "source": source_account
    }
