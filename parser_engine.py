from strategies import STRATEGY_CLASSES

def detect_and_parse(file_path: str) -> list[dict]:
    for strategy_class in STRATEGY_CLASSES:
        parser = strategy_class()
        try:
            if parser.applies_to(file_path):
                print(f"[ParserEngine] Using {parser.__class__.__name__}")
                return parser.parse(file_path)
        except Exception as e:
            print(f"[ParserEngine] Error in {parser.__class__.__name__}: {e}")

    print("[ParserEngine] No suitable parser found.")
    raise Exception("No suitable parser found for this document.")
