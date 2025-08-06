import fitz
from strategies import STRATEGY_CLASSES

def detect_and_parse(contents):
    with fitz.open("pdf", contents) as doc:
        raw_text = "\n".join(page.get_text() for page in doc)

    print("[ParserEngine] Running parser detection on in-memory PDF content")
    for strategy_class in STRATEGY_CLASSES:
        if strategy_class.matches(raw_text):
            print(f"[ParserEngine] Using {strategy_class.__name__}")
            parser = strategy_class(contents)  # FIXED: pass PDF bytes
            return parser

    raise Exception("No suitable parser found for this document.")
