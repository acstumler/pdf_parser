import fitz
import re
from .base_parser import BaseParser


class AmexMultilineParser(BaseParser):
    def parse(self):
        text = self.extract_text()
        lines = text.splitlines()
        transactions = []

        current = []
        for line in lines:
            if self.line_starts_transaction(line):
                if current:
                    tx = self.parse_block(current)
                    if tx:
                        transactions.append(tx)
                    current = []
            current.append(line)

        if current:
            tx = self.parse_block(current)
            if tx:
                transactions.append(tx)

        print(f"[AmexMultilineParser] Parsed {len(transactions)} transactions")
        return transactions

    def line_starts_transaction(self, line):
        return re.match(r"^\d{2}/\d{2}/\d{2}", line.strip())

    def parse_block(self, block):
        full_text = " ".join(block).strip()
        date_match = re.search(r"\d{2}/\d{2}/\d{2}", full_text)
        amount_match = re.search(r"(-?\$?\(?\d{1,3}(?:,\d{3})*(?:\.\d{2})\)?)", full_text)

        if not date_match or not amount_match:
            return None

        date = date_match.group()
        raw_amount = amount_match.group()
        amount = self.clean_amount(raw_amount)

        memo = full_text.replace(date, "").replace(raw_amount, "").strip()
        memo = re.sub(r"[\s]{2,}", " ", memo)[:80]

        return {
            "date": date,
            "memo": memo,
            "amount": amount,
            "source": "AMEX 61005"
        }

    def clean_amount(self, raw):
        clean = raw.replace("$", "").replace(",", "")
        if "(" in clean and ")" in clean:
            clean = "-" + clean.replace("(", "").replace(")", "")
        try:
            return round(float(clean), 2)
        except ValueError:
            return None

    @staticmethod
    def matches(text: str) -> bool:
        return (
            "AMERICAN EXPRESS" in text.upper()
            and "SUMMARY" in text.upper()
            and "PAYMENT" in text.upper()
        )
