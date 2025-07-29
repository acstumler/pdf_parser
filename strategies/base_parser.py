class BaseParser:
    def applies_to(self, file_path: str) -> bool:
        raise NotImplementedError

    def parse(self, file_path: str) -> list[dict]:
        raise NotImplementedError
