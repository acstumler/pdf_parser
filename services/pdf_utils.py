import pdfplumber
from io import BytesIO

def extract_text_from_pdf(file_contents: bytes) -> str:
    with pdfplumber.open(BytesIO(file_contents)) as pdf:
        return "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
