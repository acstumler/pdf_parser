import re
import pdfplumber
from .base_parser import BaseParser

EXCLUDE_KEYWORDS = [
    "MOBILE PAYMENT", "PAYMENT - THANK YOU",
    "INTEREST CHARGE", "CREDIT BALANCE",
    "LATE FEE", "RETURNED PAYMENT"
]

class AmexMultilineParser(BaseParser):
    def applies_to(self, file_path: str) -> bool:
        try:
            with pdfplumber.open(file_path) as pdf:
                all_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as e:
            print(f"[AmexMultilineParser] PDFPlumber failed: {e}")
            return False

        has_account = bool(re.search(r"Account Ending[^\d]*(\d{4,6})", all_text, re.IGNORECASE))
        has_dates = bool(re.search(r"\d{2}/\d{2}/\d{2,4}", all_text))
        has_amounts = bool(re.search(r"\$\d{1,5}\.\d{2}", all_text))

        print(f"[AmexMultilineParser] Detected has_account={has_account}, has_dates={has_dates}, has_amounts={has_amounts}")
        return sum([has_account, has_dates, has_amounts]) >= 2

    def parse(self, file_path: str) -> list[dict]:
        try:
            with pdfplumber.open(file_path) as pdf:
                lines = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        lines.extend(text.splitlines())
        except Exception as e:
            print(f"[AmexMultilineParser] Failed to extract PDF text: {e}")
            return []

        source = self.extract_source(lines)
        transactions = []
        current_block = []

        for line in lines:
            if self.is_transaction_start(line):
                if current_block:
                    tx = self.parse_block(current_block, source)
                    if tx:
                        transactions.append(tx)
                    current_block = []
            current_block.append(line)

        if current_block:
            tx = self.parse_block(current_block, source)
            if tx:
                transactions.append(tx)

        print(f"[AmexMultilineParser] Parsed {len(transactions)} transactions")
        return transactions

    def extract_source(self, lines) -> str:
        for line in lines:
            match = re.search(r"Account Ending[^\d]*(\d{4,6})", line, re.IGNORECASE)
            if match:
                return f"AMEX {match.group(1)}"
        return "Unknown"

    def is_transaction_start(self, line: str) -> bool:
        return bool(re.match(r"\d{2}/\d{2}/\d{2,4}", line.strip()))

    def parse_block(self, block, source):
        full_text = " ".join(block).strip()

        # Filter out known non-merchant noise
        if any(keyword in full_text.upper() for keyword in EXCLUDE_KEYWORDS):
            return None

        date_match = re.search(r"\d{2}/\d{2}/\d{2,4}", full_text)
        amount_match = re.search(r"\$?(-?\(?\d{1,4}(?:,\d{3})*(?:\.\d{2})\)?)", full_text)

        if not date_match or not amount_match:
            return None

        raw_date = date_match.group(0)
        raw_amount = amount_match.group(1)

        try:
            amount = float(raw_amount.replace("(", "-").replace(")", "").replace("$", "").replace(",", ""))
        except:
            return None

        memo = full_text.replace(raw_date, "").replace(raw_amount, "")
        memo = re.sub(r"[\s]{2,}", " ", memo).strip()

        return {
            "date": raw_date,
            "memo": memo[:80] or "Unknown",
            "amount": amount,
            "source": source
        }
