import re
from .base_parser import BaseParser

class AmexMultilineParser(BaseParser):
    def applies_to(self, file_path: str) -> bool:
        with open(file_path, "rb") as f:
            text = f.read().decode(errors="ignore")
        return "Account Ending" in text and "AMERICAN EXPRESS" in text

    def parse(self, file_path: str) -> list[dict]:
        with open(file_path, "rb") as f:
            text = f.read().decode(errors="ignore")

        source_match = re.search(r"Account Ending[^\d]*(\d{5})", text)
        source = f"AMEX {source_match.group(1)}" if source_match else "Unknown"

        lines = text.splitlines()
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

        return transactions

    def is_transaction_start(self, line):
        return bool(re.match(r"\d{2}/\d{2}/\d{2,4}", line.strip()))

    def parse_block(self, block, source):
        full_text = " ".join(block).strip()
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
            "source": source
        }
