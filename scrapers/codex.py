from .base import BaseScraper


class CodexScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name="Codex CLI",
            url="https://github.com/openai/codex/releases"
        )
