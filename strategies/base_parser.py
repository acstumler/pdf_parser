import fitz  # PyMuPDF

class BaseParser:
    def __init__(self, path):
        self.path = path

    def extract_text(self):
        with fitz.open(self.path) as doc:
            text = ""
            for page in doc:
                text += page.get_text()
        return text
