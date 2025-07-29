from .base_parser import BaseParser

class OCRParser(BaseParser):
    def __init__(self, path):
        self.path = path

    @staticmethod
    def matches(text: str) -> bool:
        return "scanned image" in text.lower() or "ocr" in text.lower()

    def parse(self):
        # Placeholder logic for OCR
        print("[OCRParser] Detected but not yet implemented.")
        return []
