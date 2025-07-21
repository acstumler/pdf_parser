import uuid
import re
from datetime import datetime

DATE_REGEX = re.compile(r'^\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}')
AMOUNT_REGEX = re.compile(r'-?\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})')

def clean_memo(raw_memo: str) -> str:
    memo = raw_memo.strip()
    memo = re.sub(r'\b\d{5,}\b', '', memo)
    memo = re.sub(r'[*]', '', memo)
    memo = re.sub(r'\s{2,}', ' ', memo)
    return memo.strip()

def clean_amount(raw_amount: str) -> float | None:
    cleaned = raw_amount.replace('$', '').replace(',', '').replace('(', '-').replace(')', '')
    try:
        return float(cleaned)
    except ValueError:
        return None

def is_probably_transaction(line: str, amount: float, memo: str) -> bool:
    return DATE_REGEX.match(line) and amount is not None and len(memo.strip()) >= 3

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
        source = page.get("source", "")
        section = page.get("section", "")
        lines = page.get("lines", [])
        print(f"--- Processing page {page.get('page_number')} with {len(lines)} lines")

        i = 0
        while i < len(lines):
            line_text = lines[i].get("text", "").strip()
            print("Line:", line_text)
            date_match = DATE_REGEX.match(line_text)

            if date_match:
                date_str = date_match.group(0).replace('-', '/').replace('.', '/')
                try:
                    parsed_date = datetime.strptime(date_str, "%m/%d/%Y").strftime("%m/%d/%Y")
                except ValueError:
                    i += 1
                    continue

                memo_lines = [line_text]
                amount = None
                for j in range(1, 6):
                    if i + j >= len(lines):
                        break
                    next_line = lines[i + j].get("text", "").strip()
                    amt_match = AMOUNT_REGEX.search(next_line)
                    if amt_match:
                        amount_val = clean_amount(amt_match.group(0))
                        if amount_val is not None:
                            amount = amount_val
                            i += j
                            break
                    else:
                        memo_lines.append(next_line)

                full_memo = " ".join(memo_lines)
                stripped_memo = re.sub(DATE_REGEX, '', full_memo)
                stripped_memo = re.sub(AMOUNT_REGEX, '', stripped_memo)
                cleaned_memo = clean_memo(stripped_memo)

                txn_type, account, classification_source = classify_type_and_account(cleaned_memo)

                if is_probably_transaction(line_text, amount or 0, cleaned_memo):
                    print(f"+++ Added transaction: {txn_type} | {cleaned_memo} | ${amount}")
                    transactions.append({
                        "id": str(uuid.uuid4()),
                        "date": parsed_date,
                        "memo": cleaned_memo,
                        "amount": amount,
                        "type": txn_type,
                        "account": account,
                        "classificationSource": classification_source,
                        "source": source,
                        "section": section,
                        "uploadedFrom": "",
                        "uploadedAt": None
                    })

            i += 1

    print(f">>> Final transaction count: {len(transactions)}")
    return { "transactions": transactions }
