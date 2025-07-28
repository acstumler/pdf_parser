from pdf_parser.raw_parser import extract_visual_rows_v2
from pdf_parser.utils.clean_vendor_name import clean_vendor_name
from pdf_parser.utils.classifyTransaction import classifyTransaction

def extract_transactions(text):
    raw_blocks = extract_visual_rows_v2(text)
    transactions = []

    for block in raw_blocks:
        try:
            amount_match = re.search(r"(\$\(?\d{1,3}(?:,\d{3})*(?:\.\d{2})?\)?)", block)
            date_match = re.search(r"\d{2}/\d{2}/\d{2,4}", block)

            amount = amount_match.group(1).replace('$', '').replace(',', '') if amount_match else None
            date = date_match.group(0) if date_match else None

            if not amount or not date:
                continue

            amt = float(amount.replace("(", "-").replace(")", ""))

            memo = clean_vendor_name(block)
            classification = classifyTransaction(memo).get("classification", "7090 - Uncategorized Expense")

            transactions.append({
                "date": date,
                "memo": memo,
                "account": classification,
                "source": "Unknown",
                "amount": f"${amt:,.2f}" if amt >= 0 else f"(${abs(amt):,.2f})"
            })
        except Exception:
            continue

    return transactions
