from raw_parser import extract_transactions_multiline
from utils.classifyTransaction import classifyTransaction
from utils.clean_vendor_name import clean_vendor_name

def extract_visual_rows_v2(pdf_path):
    raw_txns = extract_transactions_multiline(pdf_path)
    parsed = []

    for txn in raw_txns:
        cleaned_memo = clean_vendor_name(txn["memo"])
        amount = txn["amount"]

        classification = classifyTransaction(cleaned_memo, amount).get("classification", "7090 - Uncategorized Expense")

        parsed.append({
            "date": txn["date"],
            "memo": cleaned_memo,
            "amount": f"(${abs(amount):,.2f})" if amount < 0 else f"${amount:,.2f}",
            "account": classification,
            "source": "AMEX 61005"  # You can dynamically extract source if needed
        })

    return parsed
