from utils.clean_vendor_name import clean_vendor_name

# Placeholder in-memory vendor map (expand as needed)
vendor_map = {
    "Starbucks": "Meals & Entertainment",
    "Chipotle": "Meals & Entertainment",
    "Uber": "Travel",
    "Delta Airlines": "Travel",
    "Apple": "Software Subscriptions",
    "Amazon": "Office Supplies",
    "Venmo": "7090 - Uncategorized Expense",
    "Paypal": "7090 - Uncategorized Expense",
}

def classifyTransaction(memo: str, amount: float):
    cleaned_memo = clean_vendor_name(memo)
    for vendor, account in vendor_map.items():
        if vendor.lower() in cleaned_memo.lower():
            return {
                "classification": account,
                "source": "vendor_map",
                "confidenceScore": 1
            }

    return {
        "classification": "7090 - Uncategorized Expense",
        "source": "default",
        "confidenceScore": 0
    }
