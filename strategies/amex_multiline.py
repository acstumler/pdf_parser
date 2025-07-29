import re
from .base_parser import BaseParser

class AmexMultilineParser(BaseParser):
    def applies_to(self, file_path: str) -> bool:
        try:
            with open(file_path, "rb") as f:
                text = f.read().decode(errors="ignore")
            print("=== RAW PDF TEXT PREVIEW START ===")
            print(text[:3000])  # Only preview the first 3000 characters
            print("=== RAW PDF TEXT PREVIEW END ===")
        except Exception as e:
            print(f"[AmexMultilineParser] Failed to read file: {e}")
            return False

        # Always return True for now to ensure the parser runs
        return True

    def parse(self, file_path: str) -> list[dict]:
        with open(file_path, "rb") as f:
            lines = f.read().decode(errors="ignore").splitlines()

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
