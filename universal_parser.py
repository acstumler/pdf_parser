import os
from raw_parser import extract_visual_rows_v2
from utils.classifyTransaction import classifyTransaction
from utils.clean_vendor_name import clean_vendor_name

def extract_transactions(file_path):
    raw_rows = extract_visual_rows_v2(file_path)

    transactions = []
    for row in raw_rows:
        date = row.get("date")
        memo_raw = row.get("memo", "")
        amount = row.get("amount", 0.0)
        source = row.get("source", "Unknown")

        # Clean vendor/memo
        memo_clean = clean_vendor_name(memo_raw)

        # Classify using memo and amount
        classification = classifyTransaction((memo_clean, amount)).get("classification", "7090 - Uncategorized Expense")

        # Format amount for display
        formatted_amount = f"${abs(amount):,.2f}" if amount >= 0 else f"(${abs(amount):,.2f})"

        transactions.append({
            "date": date,
            "memo": memo_clean,
            "account": classification,
            "source": source,
            "amount": formatted_amount,
        })

    return transactions
