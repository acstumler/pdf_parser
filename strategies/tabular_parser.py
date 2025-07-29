from .base_parser import BaseParser

class TabularParser(BaseParser):
    def __init__(self, path):
        self.path = path

    @staticmethod
    def matches(text: str) -> bool:
        return "DATE" in text.upper() and "DESCRIPTION" in text.upper() and "AMOUNT" in text.upper()

    def parse(self):
        # Placeholder logic for tabular format
        print("[TabularParser] Detected but not yet implemented.")
        return []
