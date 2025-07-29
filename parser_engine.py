import os
from raw_parser import extract_visual_rows_v2
from utils.classify_transaction import classifyTransaction
from utils.clean_vendor_name import clean_vendor_name

async def extract_visual_rows_v2(file_path: str):
    raw = extract_visual_rows_v2(file_path)  # accepts string path

    transactions = []
    for r in raw:
        date = r.get("date", "")
        memo = r.get("memo", "")
        amount = r.get("amount", "")
        source = r.get("source", "Unknown")

        memo_clean = clean_vendor_name(memo)

        try:
            amount_val = float(str(amount).replace("(", "-").replace(")", "").replace(",", "").replace("$", ""))
        except:
            amount_val = 0.0

        classification = classifyTransaction(memo_clean, amount_val).get("classification", "7090 - Uncategorized Expense")
        formatted_amount = f"(${abs(amount_val):,.2f})" if amount_val < 0 else f"${amount_val:,.2f}"

        transactions.append({
            "date": date,
            "memo": memo_clean,
            "account": classification,
            "source": source,
            "amount": formatted_amount,
        })

    return transactions
