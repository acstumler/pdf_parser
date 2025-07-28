from utils.clean_vendor_name import clean_vendor_name

def classifyTransaction(data):
    if isinstance(data, str):
        memo = clean_vendor_name(data)
        amount = None
    elif isinstance(data, tuple):
        memo = clean_vendor_name(data[0])
        amount = data[1]
    elif isinstance(data, dict):
        memo = clean_vendor_name(data.get("memo", ""))
        amount = data.get("amount", None)
    else:
        memo = "Unknown"
        amount = None

    return {
        "classification": "7090 - Uncategorized Expense"
    }
