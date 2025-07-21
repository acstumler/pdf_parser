import uuid
import re
from datetime import datetime, timedelta

DATE_REGEX = re.compile(r'\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b')
AMOUNT_REGEX = re.compile(r'-?\$[\d,]+\.\d{2}')
SOURCE_REGEX = re.compile(r'Account Ending(?: in)?\s+(\d{1,2}-\d{4,5})', re.IGNORECASE)

def clean_memo(raw_memo: str) -> str:
    memo = raw_memo.strip()
    memo = re.sub(r'\b\d{5,}\b', '', memo)
    memo = re.sub(r'[%*]', '', memo)
    memo = re.sub(r'\(v\)', '', memo, flags=re.IGNORECASE)
    memo = re.sub(r'[^a-zA-Z0-9&,. -]', '', memo)
    memo = re.sub(r'\s{2,}', ' ', memo)
    return memo.strip()

def clean_amount(raw_amount: str) -> float | None:
    cleaned = raw_amount.replace('$', '').replace(',', '').replace('(', '-').replace(')', '')
    try:
        return float(cleaned)
    except ValueError:
        return None

def classify_type_and_account(memo: str) -> tuple[str, str, str]:
    memo_lower = memo.lower()
    if "interest" in memo_lower:
        return "interest", "7100 - Interest Expense", "preclassified"
    if "fee" in memo_lower:
        return "fee", "7110 - Loan Fees", "preclassified"
    if "payment" in memo_lower or "thank you" in memo_lower:
        return "payment", "Credit Card Payment", "preclassified"
    if "credit" in memo_lower or "refund" in memo_lower:
        return "credit", "4090 - Refunds and Discounts (Contra-Revenue)", "preclassified"
    return "charge", "", "default"

def should_skip_summary_interest(date_str: str, memo: str, amount: float, recent_interest_seen: bool) -> bool:
    memo_lower = memo.lower()
    if not any(kw in memo_lower for kw in ["interest", "pay over time", "apr"]):
        return False
    try:
        txn_date = datetime.strptime(date_str, "%m/%d/%Y")
        if txn_date < datetime(2023, 10, 1) and recent_interest_seen:
            return True
    except:
        pass
    return False

def extract_transactions(raw_pages, learned_memory):
    transactions = []
    recent_interest_seen = False

    for page in raw_pages:
        section = page.get("section", "")
        lines = page.get("lines", [])

        current_source = ""
        for line_data in lines:
            line_text = line_data.get("text", "")
            match = SOURCE_REGEX.search(line_text)
            if match:
                current_source = f"AMEX {match.group(1)}"
                break

        i = 0
        while i < len(lines):
            line = lines[i].get("text", "").strip()
            if not line:
                i += 1
                continue

            date_match = DATE_REGEX.search(line)
            amt_match = AMOUNT_REGEX.search(line)

            if date_match and amt_match:
                date_str = date_match.group(0).replace('-', '/').replace('.', '/')
                try:
                    parsed_date = datetime.strptime(date_str, "%m/%d/%Y").strftime("%m/%d/%Y")
                except ValueError:
                    i += 1
                    continue

                amount_val = clean_amount(amt_match.group(0))
                if amount_val is None or abs(amount_val) < 0.01:
                    i += 1
                    continue

                memo_lines = []
                if len(line) > len(date_str + amt_match.group(0)) + 6:
                    memo_lines.append(line)
                else:
                    for j in range(1, 4):
                        if i + j < len(lines):
                            memo_lines.append(lines[i + j].get("text", "").strip())

                full_memo = ' '.join(memo_lines)
                cleaned_memo = clean_memo(full_memo)
                txn_type, account, classification_source = classify_type_and_account(cleaned_memo)

                if should_skip_summary_interest(parsed_date, cleaned_memo, amount_val, recent_interest_seen):
                    i += 1
                    continue

                if txn_type == "interest":
                    recent_interest_seen = True

                transactions.append({
                    "id": str(uuid.uuid4()),
                    "date": parsed_date,
                    "memo": cleaned_memo,
                    "amount": amount_val,
                    "type": txn_type,
                    "account": account,
                    "classificationSource": classification_source,
                    "section": section,
                    "uploadedFrom": current_source or "Unknown Source",
                    "uploadedAt": None
                })

                i += 4
            else:
                i += 1

    return { "transactions": transactions }
