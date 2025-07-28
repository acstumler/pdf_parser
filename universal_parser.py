from datetime import datetime
import re
from utils.clean_vendor_name import clean_vendor_name
from utils.classifyTransaction import classifyTransaction


def extract_visual_rows_v2(text, source_hint=None, closing_date=None):
    lines = text.split("\n")

    # Try to extract account number from header (first 25 lines)
    account_match = next(
        (
            re.search(r"Account Ending(?:\s*in)? (\d{4,6})", l)
            for l in lines[:25]
            if "Account Ending" in l
        ),
        None,
    )
    last4 = account_match.group(1) if account_match else "0000"
    source = f"AMEX {last4}" if "American Express" in text or "AMEX" in text else f"Card {last4}"

    transactions = []
    date_pattern = r"^\d{2}/\d{2}/\d{2}$"

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if re.match(date_pattern, line):
            date_str = line
            memo_parts = []

            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if re.match(date_pattern, next_line):
                    break
                if re.match(r"^\$?-?\(?\d{1,4}(,\d{3})*(\.\d{2})?\)?$", next_line):
                    break
                memo_parts.append(next_line)
                i += 1

            amount_line = ""
            if i < len(lines):
                potential_amount = lines[i].strip()
                if re.search(r"\$?-?\(?\d", potential_amount):
                    amount_line = potential_amount
                    i += 1

            memo_raw = " ".join(memo_parts)
            memo = clean_vendor_name(memo_raw)
            account = classifyTransaction(memo)

            try:
                date_obj = datetime.strptime(date_str, "%m/%d/%y")
                date = date_obj.strftime("%m/%d/%y")
            except:
                continue

            try:
                amount_val = float(
                    re.sub(r"[^\d.-]", "", amount_line.replace("(", "-").replace(")", ""))
                )
                amount = f"(${abs(amount_val):,.2f})" if amount_val < 0 else f"${amount_val:,.2f}"
            except:
                amount = "$0.00"

            transactions.append(
                {
                    "date": date,
                    "memo": memo,
                    "account": account,
                    "source": source,
                    "amount": amount,
                }
            )
        else:
            i += 1

    return transactions
