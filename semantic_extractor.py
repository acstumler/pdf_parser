import re
from datetime import datetime
from dateutil import parser

def extract_semantic_blocks(text_lines):
    semantic_blocks = []
    current_block = []
    skip_page = False

    for line in text_lines:
        lowered_line = line.lower()
        if "interest charged" in lowered_line or "interest charge calculation" in lowered_line or "trailing interest" in lowered_line:
            skip_page = True
        if skip_page:
            continue

        clean_line = line.strip()

        if re.match(r'\d{2}/\d{2}/\d{2,4}', clean_line):
            if current_block:
                semantic_blocks.append(current_block)
                current_block = []
            current_block.append(clean_line)
        elif current_block:
            current_block.append(clean_line)

    if current_block:
        semantic_blocks.append(current_block)

    return semantic_blocks


def extract_transactions(text_lines):
    blocks = extract_semantic_blocks(text_lines)
    transactions = []

    for block in blocks:
        if not block:
            continue

        date_match = re.match(r'\d{2}/\d{2}/\d{2,4}', block[0])
        if not date_match:
            continue

        try:
            date_obj = parser.parse(date_match.group(0))
            date_str = date_obj.strftime("%m/%d/%Y")
        except Exception:
            continue

        full_block = " ".join(block)

        # Extract amount
        amount_match = re.findall(r"\$\s?[\d,]+\.\d{2}", full_block)
        if not amount_match:
            continue
        amount_str = amount_match[-1].replace("$", "").replace(",", "").strip()
        try:
            amount = float(amount_str)
        except Exception:
            continue

        # Simplify memo
        memo_line = next((line for line in block if any(char.isalpha() for char in line)), "")
        memo = memo_line.strip().split("  ")[0]

        transactions.append({
            "date": date_str,
            "memo": memo,
            "amount": amount
        })

    return transactions
