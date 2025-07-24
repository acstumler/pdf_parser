import io
import re
import shutil
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
from datetime import datetime, timedelta
from dateutil import parser
from utils.clean_vendor_name import clean_vendor_name

print(f"[DEBUG] Tesseract path: {shutil.which('tesseract')}")  # Confirm runtime OCR access

def extract_with_pdfplumber(pdf_bytes):
    text_lines = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines = text.split('\n')
                text_lines.extend([line.strip() for line in lines if line.strip()])
    return text_lines

def extract_with_ocr(pdf_bytes):
    ocr_lines = []
    try:
        images = convert_from_bytes(pdf_bytes)
        for img in images:
            text = pytesseract.image_to_string(img)
            lines = text.split('\n')
            ocr_lines.extend([line.strip() for line in lines if line.strip()])
    except Exception as e:
        print(f"[OCR ERROR] {e}")
    return ocr_lines

def deduplicate_lines(lines):
    seen = set()
    unique = []
    for line in lines:
        fingerprint = line.lower().strip()
        if fingerprint not in seen:
            unique.append(line)
            seen.add(fingerprint)
    return unique

EXCLUDE_MEMO_PATTERNS = [
    "continued on", "detail continued", "cash advance", "closing date",
    "account ending", "payment due", "fees", "see page", "pay over time"
]

def extract_source_account(text_lines):
    for line in text_lines:
        if "account ending" in line.lower():
            match = re.search(r"(account ending\s+)?(\d{4,6})", line, re.IGNORECASE)
            if match:
                return f"AMEX {match.group(2)}"
    return "Unknown Source"

def extract_closing_date(text_lines):
    for line in text_lines:
        if "closing" in line.lower() and "date" in line.lower():
            match = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", line)
            if match:
                try:
                    return parser.parse(match.group(1)).date()
                except:
                    continue
    return None

def build_candidate_blocks(text_lines):
    blocks = []
    current_block = []
    for line in text_lines:
        if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", line):
            if current_block:
                blocks.append(current_block)
            current_block = [line]
        elif current_block:
            current_block.append(line)
    if current_block:
        blocks.append(current_block)
    return blocks

def extract_date(block):
    try:
        return parser.parse(block[0]).date()
    except:
        return None

def parse_amount(block):
    match = re.search(r"-?\$?\d{1,3}(?:,\d{3})*\.\d{2}", " ".join(block))
    if match:
        cleaned = match.group().replace("$", "").replace(",", "")
        try:
            return float(cleaned)
        except:
            return None
    return None

def extract_memo(block):
    candidates = [
        line.strip() for line in block[1:]
        if len(line.strip()) > 3 and not is_junk_memo(line.strip())
    ]
    return max(candidates, key=len) if candidates else ""

def is_junk_memo(memo):
    lower = memo.lower()
    if any(p in lower for p in EXCLUDE_MEMO_PATTERNS):
        return True
    if re.fullmatch(r"\d{3}[-\s]?\d{3}[-\s]?\d{4}", memo):
        return True
    if not re.search(r"[a-zA-Z]{3,}", memo):
        return True
    return False

def extract_transactions_from_text(text_lines):
    transactions = []
    seen_fingerprints = set()

    end_date = extract_closing_date(text_lines) or datetime.today().date()
    start_date = end_date - timedelta(days=60)
    print(f"[INFO] Enforcing date filter: Start = {start_date}, End = {end_date}")

    source = extract_source_account(text_lines)
    blocks = build_candidate_blocks(text_lines)
    print(f"[INFO] Found {len(blocks)} candidate blocks")

    for block in blocks:
        if len(block) < 2:
            continue
        date_obj = extract_date(block)
        if not date_obj or not (start_date <= date_obj <= end_date):
            continue
        amount = parse_amount(block)
        memo = extract_memo(block)
        if not (amount and memo):
            continue
        date_str = date_obj.strftime("%m/%d/%Y")

        if "payment" in memo.lower() or "thank you" in memo.lower():
            amount = -abs(amount)

        fingerprint = f"{date_str}|{memo.lower()}|{amount:.2f}|{source}"
        if fingerprint in seen_fingerprints:
            print(f"[SKIPPED] Duplicate fingerprint: {fingerprint}")
            continue
        seen_fingerprints.add(fingerprint)

        transactions.append({
            "date": date_str,
            "memo": clean_vendor_name(memo),
            "account": "7090 - Uncategorized Expense",
            "source": source,
            "amount": amount
        })

    print(f"[INFO] Final parsed transactions: {len(transactions)}")
    return { "transactions": transactions }

def extract_transactions(pdf_bytes):
    print("[INFO] Extracting with pdfplumber + OCR")
    text_lines = extract_with_pdfplumber(pdf_bytes)
    ocr_lines = extract_with_ocr(pdf_bytes)
    combined = text_lines + ocr_lines
    deduped = deduplicate_lines(combined)
    print(f"[INFO] Total combined lines: {len(deduped)}")
    return extract_transactions_from_text(deduped)
