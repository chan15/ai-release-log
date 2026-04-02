from typing import Optional

from .base import BaseScraper
from .claude import ClaudeScraper
from .codex import CodexScraper
from .copilot import CopilotScraper
from .gemini import GeminiScraper


class ScraperFactory:
    """
    Factory class to create scraper instances.
    """

    @staticmethod
    def get_scraper(project_key: str) -> Optional[BaseScraper]:
        """
        Return a scraper instance based on the project key.
        """
        scrapers = {
            "gemini": GeminiScraper,
            "copilot": CopilotScraper,
            "codex": CodexScraper,
            "claude": ClaudeScraper
        }

        scraper_class = scrapers.get(project_key.lower())
        if scraper_class:
            return scraper_class()
        return None

    @staticmethod
    def get_all_keys():
        return ["gemini", "copilot", "codex", "claude"]
