import re
import pdfplumber
from datetime import datetime

class AmexMultilineParser:
    def __init__(self, path):
        self.path = path

    def parse(self):
        transactions = []
        with pdfplumber.open(self.path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                lines = text.splitlines()
                mode = None  # Tracks whether we're in Payments, Credits, or New Charges
                current_block = []

                for line in lines:
                    line = line.strip()

                    # Detect section changes
                    if re.search(r"^Payments$", line):
                        mode = "Payments"
                        continue
                    elif re.search(r"^Credits$", line):
                        mode = "Credits"
                        continue
                    elif re.search(r"^Detail$", line):
                        continue  # Skip section label
                    elif re.search(r"^New Charges$", line):
                        mode = "Charges"
                        continue

                    # Try to extract date
                    date_match = re.match(r"(\d{2}/\d{2}/\d{2,4})", line)
                    amount_match = re.search(r"(-?\(?\$?\d{1,4}(?:,\d{3})*(?:\.\d{2})\)?)$", line)

                    if date_match:
                        # If block exists, try to parse
                        if current_block:
                            parsed = self.parse_block(current_block, mode)
                            if parsed:
                                transactions.append(parsed)
                            current_block = []

                    current_block.append(line)

                # Parse final block
                if current_block:
                    parsed = self.parse_block(current_block, mode)
                    if parsed:
                        transactions.append(parsed)

        print(f"[AmexMultilineParser] Parsed {len(transactions)} transactions")
        return transactions

    def parse_block(self, lines, mode):
        full = " ".join(lines).strip()

        date_match = re.search(r"(\d{2}/\d{2}/\d{2,4})", full)
        amount_match = re.search(r"(-?\(?\$?\d{1,4}(?:,\d{3})*(?:\.\d{2})\)?)$", full)

        if not date_match or not amount_match:
            return None

        raw_date = date_match.group(1)
        raw_amount = amount_match.group(1)

        # Convert amount to float
        clean_amount = raw_amount.replace("$", "").replace(",", "")
        if "(" in clean_amount and ")" in clean_amount:
            clean_amount = "-" + clean_amount.replace("(", "").replace(")", "")
        try:
            amount = float(clean_amount)
        except ValueError:
            return None

        # Build memo
        memo = full.replace(raw_date, "").replace(raw_amount, "").strip()
        memo = re.sub(r"\s{2,}", " ", memo)
        memo = memo[:100]

        return {
            "date": datetime.strptime(raw_date, "%m/%d/%y").strftime("%m/%d/%Y"),
            "memo": memo or "Unknown",
            "amount": amount,
            "source": "AMEX 61005"
        }

    @staticmethod
    def matches(text):
        return "American Express" in text or "AMEX" in text
