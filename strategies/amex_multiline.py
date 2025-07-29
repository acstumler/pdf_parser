import re
from .base_parser import BaseParser


class AmexMultilineParser(BaseParser):
    def parse(self):
        text = self.extract_text()
        lines = text.splitlines()

        # Remove empty lines and strip whitespace
        lines = [line.strip() for line in lines if line.strip()]

        blocks = self.extract_transaction_blocks(lines)

        transactions = []
        for block in blocks:
            tx = self.parse_block(block)
            if tx:
                transactions.append(tx)

        print(f"[AmexMultilineParser] Parsed {len(transactions)} transactions")
        return transactions

    def extract_transaction_blocks(self, lines):
        """
        Identify contiguous blocks of lines representing transactions.
        Ignore metadata blocks (interest summary, APR tables, etc.).
        """
        blocks = []
        current_block = []

        for line in lines:
            # Reject known metadata rows
            if any(keyword in line for keyword in [
                "Interest Charge", "Total Fees", "APR", "Annual Percentage", "Fees in 2023",
                "Interest in 2023", "Pay Over Time Limit", "Cash Advances", "Total New Charges",
                "2023 Fees", "Interest Totals", "Interest Calculation", "See page", "Rewards Points",
                "Pay Over Time", "Statement Date", "Billing Period"
            ]):
                continue

            # Detect start of transaction line (most have MM/DD/YY format)
            if re.match(r"\d{2}/\d{2}/\d{2,4}", line):
                if current_block:
                    blocks.append(current_block)
                    current_block = []
            current_block.append(line)

        if current_block:
            blocks.append(current_block)

        return blocks

    def parse_block(self, block):
        full_text = " ".join(block).strip()

        date_match = re.search(r"(\d{2}/\d{2}/\d{2,4})", full_text)
        amount_match = re.search(r"(-?\(?\d{1,4}(?:,\d{3})*(?:\.\d{2})\)?)", full_text)

        if not date_match or not amount_match:
            return None

        raw_date = date_match.group(1)
        raw_amount = amount_match.group(1)

        # Clean and convert amount
        clean_amount = raw_amount.replace("(", "-").replace(")", "").replace("$", "").replace(",", "")
        try:
            amount = round(float(clean_amount), 2)
        except ValueError:
            return None

        # Remove date/amount from full text to isolate memo
        memo_text = full_text.replace(raw_date, "").replace(raw_amount, "").strip()
        memo_text = re.sub(r"[\s]{2,}", " ", memo_text)

        return {
            "date": raw_date,
            "memo": memo_text[:100].strip() or "Unknown",
            "amount": amount,
            "source": "AMEX 61005"
        }
