from io import BytesIO
import pdfplumber
from strategies.amex_multiline import AmexMultilineParser
from strategies.tabular_parser import TabularParser
from strategies.ocr_parser import OCRParser

STRATEGIES = [AmexMultilineParser, TabularParser, OCRParser]

def extract_transactions_from_bytes(pdf_bytes):
    """
    Accepts PDF bytes and returns (rows, meta)
    rows: list of dicts with transaction data
    meta: dict with at least 'source_account' and optionally 'statement_end_date'
    """
    if not pdf_bytes:
        return [], {"source_account": "", "statement_end_date": ""}

    # Extract text for matching
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text = "\n".join([page.extract_text() or "" for page in pdf.pages])
    except Exception:
        text = ""

    # Try each strategy
    for strategy_cls in STRATEGIES:
        if strategy_cls.matches(text):
            parser = strategy_cls(pdf_bytes)
            rows = parser.extract_transactions()
            meta = {
                "source_account": getattr(parser, "account_source", "") or "",
                "statement_end_date": "",
            }
            return rows or [], meta

    # No match
    return [], {"source_account": "", "statement_end_date": ""}
