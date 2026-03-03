from .base import BaseScraper


class CopilotScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name="Copilot CLI",
            url="https://github.com/github/copilot-cli/releases"
        )
