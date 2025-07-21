import uuid
import re
from datetime import datetime

DATE_REGEX = re.compile(r'\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b')
AMOUNT_REGEX = re.compile(r'-?\$[\d,]+\.\d{2}')  # Require dollar sign only
SOURCE_REGEX = re.compile(r'Account Ending(?: in)?\s+(\d{1,2}-\d{4,5})', re.IGNORECASE)

def clean_memo(raw_memo: str) -> str:
    memo = raw_memo.strip()
    memo = re.sub(r'\b\d{5,}\b', '', memo)
    memo = re.sub(r'[%*]', '', memo)
    memo = re.sub(r'\(v\)', '', memo, flags=re.IGNORECASE)
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

def extract_transactions(raw_pages, learned_memory):
    transactions = []
    print(">>> Beginning semantic transaction extraction...")

    for page in raw_pages:
        section = page.get("section", "")
        lines = page.get("lines", [])
        print(f"--- Processing page {page.get('page_number')} with {len(lines)} lines")

        # ✅ Extract uploadedFrom from PDF line text only
        current_source = ""
        for line_data in lines:
            line_text = line_data.get("text", "")
            match = SOURCE_REGEX.search(line_text)
            if match:
                current_source = f"American Express {match.group(1)}"
                print(f"✅ Found source: {current_source}")
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
                # Extract date
                date_str = date_match.group(0).replace('-', '/').replace('.', '/')
                try:
                    parsed_date = datetime.strptime(date_str, "%m/%d/%Y").strftime("%m/%d/%Y")
                except ValueError:
                    try:
                        parsed_date = datetime.strptime(date_str, "%m/%d/%y").strftime("%m/%d/%Y")
                    except ValueError:
                        print(f"Skipped: Unreadable date format -> {line}")
                        i += 1
                        continue

                # Extract amount
                amount_val = clean_amount(amt_match.group(0))
                if amount_val is None or abs(amount_val) < 0.01:
                    print(f"Skipped: Unusable amount -> {line}")
                    i += 1
                    continue

                # Build memo from nearby lines if memo is weak
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

                print(f"+++ Added transaction: {txn_type} | {cleaned_memo} | ${amount_val}")
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

    print(f">>> Final transaction count: {len(transactions)}")
    return { "transactions": transactions }
