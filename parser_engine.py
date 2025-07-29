from strategies import STRATEGY_CLASSES, AmexMultilineParser

def detect_and_parse(file_path: str) -> list[dict]:
    print(f"[ParserEngine] Running parser detection on: {file_path}")
    attempted = []

    for strategy_class in STRATEGY_CLASSES:
        parser = strategy_class()
        try:
            if parser.applies_to(file_path):
                print(f"[ParserEngine] Using {parser.__class__.__name__}")
                return parser.parse(file_path)
            else:
                attempted.append(parser.__class__.__name__)
        except Exception as e:
            print(f"[ParserEngine] Error in {parser.__class__.__name__}: {e}")

    print(f"[ParserEngine] No strategy matched. Tried: {attempted}")
    print("[ParserEngine] Fallback: forcing AmexMultilineParser for dev testing")
    return AmexMultilineParser().parse(file_path)
