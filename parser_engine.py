import fitz
from strategies import STRATEGY_CLASSES

def detect_and_parse(path):
    with fitz.open(path) as doc:
        raw_text = "\n".join(page.get_text() for page in doc)

    print(f"[ParserEngine] Running parser detection on: {path}")
    for strategy_class in STRATEGY_CLASSES:
        if strategy_class.matches(raw_text):
            print(f"[ParserEngine] Using {strategy_class.__name__}")
            parser = strategy_class(path)
            return parser.parse()

    raise Exception("No suitable parser found for this document.")
