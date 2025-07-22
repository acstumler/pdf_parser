import re

def extract_transactions_semantically(text: str, source_label: str) -> list:
    """
    Extracts transactions from OCR text using semantic pattern recognition.
    """
    lines = text.split("\n")
    transactions = []

    # Define month/day/year pattern
    date_pattern = r"\b(0?[1-9]|1[0-2])[/-](0?[1-9]|[12][0-9]|3[01])[/-](\d{2}|\d{4})\b"
    amount_pattern = r"\$?\(?-?\d{1,3}(?:,\d{3})*(?:\.\d{2})?\)?"

    # Maintain state for a possible transaction
    current_transaction = {}

    for i, line in enumerate(lines):
        clean_line = line.strip()

        # Skip lines that are not semantically transactions
        if not clean_line:
            continue
        if "Interest Charge Calculation" in clean_line or "Interest Charged" in clean_line:
            continue
        if "Pay Over Time" in clean_line or "Cash Advances" in clean_line:
            continue
        if "Minimum Payment" in clean_line or "Payment Due" in clean_line:
            continue
        if "ALANSON STUMLER" in clean_line:
            continue
        if re.search(r"Page \d+ of \d+", clean_line, re.IGNORECASE):
            continue
        if re.search(r"Total Interest Charged", clean_line, re.IGNORECASE):
            continue

        # Look for date
        date_match = re.search(date_pattern, clean_line)
        if date_match:
            current_transaction["date"] = date_match.group(0)

        # Look for amount (skip negative/refund entries for now)
        amount_match = re.search(amount_pattern, clean_line)
        if amount_match:
            raw_amount = amount_match.group(0).replace("$", "").replace(",", "")
            try:
                value = float(raw_amount.strip("()"))
                if "(" in raw_amount or ")" in raw_amount:
                    value = -value
                current_transaction["amount"] = round(value, 2)
            except ValueError:
                continue

        # Look for vendor/memo line
        if any(keyword in clean_line.lower() for keyword in ["llc", "inc", "restaurant", "coffee", "bar", "pay", "kroger", "paypal", "venmo", "target", "walmart", "starbucks", "store", "center", "stadium", "liquors", "apple.com", "deli", "chicken", "pizza", "cardinal", "tazikis", "autozone"]):
            current_transaction["memo"] = clean_line

        # If all pieces present, store the transaction
        if "date" in current_transaction and "amount" in current_transaction and "memo" in current_transaction:
            transactions.append({
                "date": current_transaction["date"],
                "memo": current_transaction["memo"].title(),
                "amount": current_transaction["amount"],
                "source": source_label
            })
            current_transaction = {}

    return transactions
