import re
from pdfplumber.page import Page
from typing import List, Dict
from utils.clean_vendor_name import clean_vendor_name

def extract_transactions(text_lines: List[str]) -> List[Dict]:
    transactions = []
    current_date = ""
    for line in text_lines:
        match = re.match(r"(\d{2}/\d{2}/\d{2,4})\s+(.*)\s+\$([0-9,]+\.\d{2})", line)
        if match:
            date, raw_memo, raw_amount = match.groups()
            memo = clean_vendor_name(raw_memo)
            amount = float(raw_amount.replace(',', ''))
            if "CREDIT" in raw_memo.upper() or "PAYMENT" in raw_memo.upper() or amount < 0:
                amount = -abs(amount)
            transactions.append({
                "date": format_date(date),
                "memo": memo,
                "account": "7090 - Uncategorized Expense",
                "source": "Unknown Source",
                "amount": round(amount, 2),
            })
    return transactions

def format_date(raw: str) -> str:
    parts = raw.split("/")
    mm = parts[0].zfill(2)
    dd = parts[1].zfill(2)
    yyyy = parts[2]
    if len(yyyy) == 2:
        yyyy = "20" + yyyy
    return f"{mm}/{dd}/{yyyy}"
