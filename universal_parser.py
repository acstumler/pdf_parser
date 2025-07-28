from raw_parser import extract_visual_rows_v2 as extract_transactions
from utils.classifyTransaction import classifyTransaction
from utils.clean_vendor_name import clean_vendor_name

def extract_transactions(file_path):
    raw = extract_transactions(file_path)
    transactions = []

    for item in raw:
        date = item.get("date", "").strip()
        memo_raw = item.get("memo", "").strip()
        amount = item.get("amount", 0)
        source = item.get("source", "Unknown")

        # Clean the memo
        memo = clean_vendor_name(memo_raw)

        # Classify the account based on memo and amount
        classification = classifyTransaction((memo, amount)).get("classification", "7090 - Uncategorized Expense")

        transactions.append({
            "date": date,
            "memo": memo,
            "account": classification,
            "source": source,
            "amount": amount
        })

    return transactions
