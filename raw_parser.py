import re

def extract_visual_rows_v2(file_path):
    with open(file_path, "rb") as f:
        text = f.read().decode(errors="ignore")

    lines = text.splitlines()
    transactions = []
    current_block = []

    for line in lines:
        if re.search(r"\d{2}/\d{2}/\d{2,4}", line) and re.search(r"\$\d", line):
            if current_block:
                transactions.append(parse_block(current_block))
                current_block = []
        current_block.append(line)

    if current_block:
        transactions.append(parse_block(current_block))

    return [tx for tx in transactions if tx]

def parse_block(block):
    text = " ".join(block)
    date_match = re.search(r"\d{2}/\d{2}/\d{2,4}", text)
    amt_match = re.search(r"-?\$?\(?\d+[\.,]?\d*\)?", text)

    if not date_match or not amt_match:
        return None

    date = date_match.group(0)
    raw_amount = amt_match.group(0)
    clean_amount = raw_amount.replace("(", "-").replace(")", "").replace("$", "").replace(",", "")
    
    try:
        amount = round(float(clean_amount), 2)
    except ValueError:
        return None

    memo = text
    return {
        "date": date,
        "memo": memo,
        "amount": amount,
        "source": "Unknown"
    }
