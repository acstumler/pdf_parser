import re
from pdf_parser.base_parser import BaseStatementParser

class AmexMultilineParser(BaseStatementParser):
    def __init__(self):
        super().__init__()
        self.account_source = None

    def extract_transactions(self, text: str):
        pages = text.split("---- PAGE ")
        all_lines = []
        for page in pages:
            lines = page.split("\n")
            for line in lines:
                clean = line.strip()
                if clean:
                    all_lines.append(clean)

        source = self._extract_source_account(all_lines)
        self.account_source = source

        candidates = self._group_transaction_blocks(all_lines)
        parsed = [self._parse_block(block) for block in candidates]
        return [p for p in parsed if p]

    def _group_transaction_blocks(self, lines):
        blocks = []
        current = []

        for line in lines:
            if re.match(r"^\d{2}/\d{2}/\d{2,4}", line.strip()):
                if current:
                    blocks.append(current)
                current = [line.strip()]
            elif current:
                current.append(line.strip())

        if current:
            blocks.append(current)

        return blocks

    def _extract_source_account(self, lines):
        for line in lines:
            match = re.search(r"Account Ending[^\d]*(\d{5})", line, re.IGNORECASE)
            if match:
                return f"AMEX {match.group(1)}"
        return "AMEX"

    def _parse_block(self, block):
        full_text = " ".join(block).strip()

        date_match = re.search(r"(\d{2}/\d{2}/\d{2,4})", full_text)
        amount_match = re.search(r"(-?\$?\(?\d{1,4}(?:,\d{3})*(?:\.\d{2})\)?)", full_text)

        if not date_match or not amount_match:
            return None

        raw_date = date_match.group(1)
        raw_amount = amount_match.group(1)

        # Normalize and invert amount if shown as a credit (parentheses or leading minus)
        clean_amount = (
            raw_amount.replace("(", "-")
            .replace(")", "")
            .replace("$", "")
            .replace(",", "")
        )

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
