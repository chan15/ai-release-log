from .base import BaseScraper


class ClaudeScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name="Claude Code",
            url="https://github.com/anthropics/claude-code/releases"
        )

