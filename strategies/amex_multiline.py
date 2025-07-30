import re
from pdfplumber import open as pdfopen
from .base_parser import BaseParser

class AmexMultilineParser(BaseParser):
    def __init__(self, path):
        self.path = path

    @staticmethod
    def matches(text: str) -> bool:
        return "AMERICAN EXPRESS" in text.upper() and "ACCOUNT ENDING" in text.upper()

    def extract_text(self):
        with pdfopen(self.path) as pdf:
            return "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    def parse(self):
        text = self.extract_text()
        lines = text.split("\n")

        transactions = []
        current_block = []

        def is_valid_line(line):
            line = line.strip()
            # Must start with a date and contain a dollar value
            return bool(re.match(r"^\d{2}/\d{2}/\d{2,4}", line) and "$" in line)

        for line in lines:
            if is_valid_line(line):
                if current_block:
                    tx = self._parse_block(current_block)
                    if tx:
                        transactions.append(tx)
                    current_block = []
            current_block.append(line)

        # Final block catch
        if current_block:
            tx = self._parse_block(current_block)
            if tx:
                transactions.append(tx)

        return transactions

    def _parse_block(self, block):
        full_text = " ".join(block).strip()

        # Removed "interest charge" from exclusions to capture interest transactions
        if any(exclusion in full_text.lower() for exclusion in [
            "apr", "fees in 2023", "minimum payment"
        ]):
            return None

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

        # Allow long, repeated memo strings; just clean spacing
        memo_text = full_text.replace(raw_date, "").replace(raw_amount, "").strip()
        memo_text = re.sub(r"[\s]{2,}", " ", memo_text)
        memo = memo_text[:80].strip() or "Unknown"

        return {
            "date": raw_date,
            "memo": memo,
            "amount": amount,
            "source": "AMEX 61005"
        }
