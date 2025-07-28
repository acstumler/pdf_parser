from pdf_parser.utils.clean_vendor_name import clean_vendor_name

def classifyTransaction(data):
    memo = data if isinstance(data, str) else data.get("memo", "")
    name = clean_vendor_name(memo)

    # Default fallback classification
    return {
        "classification": "7090 - Uncategorized Expense"
    }
