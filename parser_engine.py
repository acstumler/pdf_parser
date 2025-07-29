import os
import fitz  # PyMuPDF
from strategies.amex_multiline import AmexMultilineParser

STRATEGIES = [
    AmexMultilineParser,
]

def detect_and_parse(path):
    with fitz.open(path) as doc:
        raw_text = "\n".join(page.get_text() for page in doc)

    print(f"[ParserEngine] Running parser detection on: {path}")
    for strategy_class in STRATEGIES:
        if strategy_class.matches(raw_text):
            print(f"[ParserEngine] Using {strategy_class.__name__}")
            parser = strategy_class(path)
            return parser.parse()

    raise Exception("No suitable parser found for this document.")
