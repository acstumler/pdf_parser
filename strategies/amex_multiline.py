import re
from pdfplumber import open as pdfopen
from .base_parser import BaseParser

class AmexMultilineParser(BaseParser):
    def __init__(self, path):
        self.path = path
        self.account_source = "Unknown Source"

    @staticmethod
    def matches(text: str) -> bool:
        has_dates_and_amounts = bool(re.search(r"\d{2}/\d{2}/\d{2,4}.*\$-?\(?\d", text))
        has_fee_section_structure = bool(re.search(r"Total\s+Fees\s+for\s+this\s+Period", text, re.IGNORECASE))
        has_interest_section_structure = bool(re.search(r"Interest\s+Charged", text, re.IGNORECASE))
        has_posted_dollar_asterisk = bool(re.search(r"\$\d+\.\d{2}\*", text))

        score = sum([
            has_dates_and_amounts,
            has_fee_section_structure,
            has_interest_section_structure,
            has_posted_dollar_asterisk
        ])
        return score >= 2

    def extract_text(self):
        with pdfopen(self.path) as pdf:
            text = []
            for page_number, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                print(f"\n---- PAGE {page_number + 1} ----\n")
                print(page_text or "[EMPTY]")
                if page_text:
                    text.append(page_text)
                    match = re.search(r"Account\s*Ending[-\s]*(?:\d-)?(\d{5})", page_text, re.IGNORECASE)
                    if match:
                        self.account_source = f"AMEX {match.group(1)}"
                        print(f"[DEBUG] Extracted Source: {self.account_source}")
                    else:
                        print(f"[DEBUG] No source match on page {page_number + 1}")
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

        if re.search(r"(new balance|min.*payment|membership rewards|account summary|customer care|gold card|p\.\s*\d+/)", memo.lower()):
            return None

        if re.fullmatch(r"[\d\.\s-]+", memo):
            return None
        if memo.lower() in ["unknown", "", "$", "-", "–"]:
            return None

        return {
            "date": raw_date,
            "memo": memo,
            "amount": amount,
            "source": self.account_source
        }
