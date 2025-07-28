from utils.clean_vendor_name import clean_vendor_name

def classifyTransaction(memo: str, amount: float):
    cleaned_memo = clean_vendor_name(memo)

    return {
        "classification": "7090 - Uncategorized Expense",
        "source": "unclassified",
        "confidenceScore": 0
    }
