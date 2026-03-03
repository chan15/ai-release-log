from .base import BaseScraper


class GeminiScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name="Gemini CLI",
            url="https://github.com/google-gemini/gemini-cli/releases"
        )
