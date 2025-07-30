import re
from pdfplumber import open as pdfopen
from .base_parser import BaseParser

class AmexMultilineParser(BaseParser):
    def __init__(self, path):
        self.path = path
        self.account_source = "Unknown Source"

    @staticmethod
    def matches(text: str) -> bool:
        # Detect AMEX-style structure based on repeating date + amount lines and known layout phrases
        has_dates_and_dollars = bool(re.search(r"\d{2}/\d{2}/\d{2,4}.*\$-?\(?\d", text))
        has_fees_section = "Total Fees for this Period" in text
        has_interest_section = "Interest Charged" in text
        return has_dates_and_dollars and (has_fees_section or has_interest_section)

    def extract_text(self):
        with pdfopen(self.path) as pdf:
            text = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
                    # Detect account number (last 5 digits) from header
                    match = re.search(r"Account Ending[^\d]*(\d{5})", page_text, re.IGNORECASE)
                    if match:
                        self.account_source = match.group(1)
            return "\n".join(text)

    def parse(self):
        text = self.extract_text()
        lines = text.split("\n")

        transactions = []
        current_block = []

        def is_valid_line(line):
            line = line.strip()
            return bool(re.match(r"^\d{2}/\d{2}/\d{2,4}", line) and "$" in line)

        for line in lines:
            if is_valid_line(line):
                if current_block:
                    tx = self._parse_block(current_block)
                    if tx:
                        transactions.append(tx)
                    current_block = []
            current_block.append(line)

        if current_block:
            tx = self._parse_block(current_block)
            if tx:
                transactions.append(tx)

        return transactions

    def _parse_block(self, block):
        full_text = " ".join(block).strip()

        # No keyword filters — allow all valid entries including interest
        date_match = re.search(r"(\d{2}/\d{2}/\d{2,4})", full_text)
        amount_match = re.search(r"\$?(-?\(?\d{1,4}(?:,\d{3})*(?:\.\d{2})\)?)", full_text)

        if not date_match or not amount_match:
            return None

        raw_date = date_match.group(1)
        raw_amount = amount_match.group(1)
        clean_amount = raw_amount.replace("(", "-").replace(")", "").replace("$", "").replace(",", "")

        try:
            amount = round(float(clean_amount), 2)
        except ValueError:
            return None

        memo_text = full_text.replace(raw_date, "").replace(raw_amount, "").strip()
        memo_text = re.sub(r"[\s]{2,}", " ", memo_text)
        memo = memo_text[:80].strip() or "Unknown"

        return {
            "date": raw_date,
            "memo": memo,
            "amount": amount,
            "source": self.account_source
        }
