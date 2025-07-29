from strategies import STRATEGY_CLASSES

def detect_and_parse(file_path: str) -> list[dict]:
    for strategy_class in STRATEGY_CLASSES:
        parser = strategy_class()
        if parser.applies_to(file_path):
            return parser.parse(file_path)
    raise Exception("No suitable parser found for this document.")
