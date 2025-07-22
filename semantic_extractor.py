import uuid
import re
from datetime import datetime

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

def looks_like_summary_interest_row(memo, date_str, amount):
    memo_lower = (memo or "").lower()
    if not any(kw in memo_lower for kw in ["interest", "pay over time", "apr", "summary"]):
        return False
    try:
        txn_date = datetime.strptime(date_str, "%m/%d/%Y")
        return txn_date < datetime(2023, 10, 1)
    except:
        return False

def extract_transactions(raw_pages, learned_memory):
    transactions = []
    current_source = ""

    for page in raw_pages:
        section = page.get("section", "")
        lines = page.get("lines", [])

        # Get source from any line
        for line_data in lines:
            text = line_data.get("text", "")
            match = SOURCE_REGEX.search(text)
            if match:
                current_source = f"AMEX {match.group(1)}"
                break

        print(f"\n--- Processing Page with {len(lines)} lines ---")
        i = 0
        while i < len(lines):
            line = lines[i].get("text", "").strip()
            print(f"[Line {i}] Raw: {line}")

            date_match = DATE_REGEX.search(line)
            if date_match:
                date_str = date_match.group(0).replace('-', '/').replace('.', '/')
                try:
                    parsed_date = datetime.strptime(date_str, "%m/%d/%Y").strftime("%m/%d/%Y")
                except ValueError:
                    i += 1
                    continue

                # Look ahead for amount and memo
                memo_lines = []
                amount_val = None

                for j in range(1, 7):  # next 6 lines
                    if i + j < len(lines):
                        next_line = lines[i + j].get("text", "").strip()
                        amt_match = AMOUNT_REGEX.search(next_line)
                        if amt_match and amount_val is None:
                            amount_val = clean_amount(amt_match.group(0))
                        else:
                            memo_lines.append(next_line)

                full_memo = ' '.join(memo_lines).strip()
                cleaned_memo = clean_memo(full_memo)

                if looks_like_summary_interest_row(cleaned_memo, parsed_date, amount_val):
                    print(f"✘ Skipping interest summary: {parsed_date} - {cleaned_memo}")
                    i += 1
                    continue

                if amount_val is not None and cleaned_memo:
                    txn = {
                        "id": str(uuid.uuid4()),
                        "date": parsed_date,
                        "memo": cleaned_memo,
                        "amount": amount_val,
                        "type": "charge",
                        "account": "",
                        "classificationSource": "default",
                        "section": section,
                        "uploadedFrom": current_source or "Unknown Source",
                        "uploadedAt": None
                    }
                    transactions.append(txn)
                    print(f"✓ Added TXN: {parsed_date} - {cleaned_memo} - ${amount_val:.2f}")

                i += 6  # skip past chunk
            else:
                i += 1

    print(f"\n✅ Finished. Parsed {len(transactions)} transactions.")
    return { "transactions": transactions }
