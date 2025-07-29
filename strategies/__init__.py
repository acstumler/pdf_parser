from .amex_multiline import AmexMultilineParser
from .tabular_parser import TabularParser
from .ocr_parser import OCRParser

STRATEGY_CLASSES = [
    AmexMultilineParser,
    TabularParser,
    OCRParser,
]
