import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional
from .base import BaseScraper


class AntigravityScraper(BaseScraper):
    """
    Scraper for the Antigravity CLI CHANGELOG.md page on GitHub.
    """

    def __init__(self):
        super().__init__(
            name="Antigravity CLI",
            url="https://github.com/google-antigravity/antigravity-cli/blob/main/CHANGELOG.md"
        )

    def fetch_latest_release(self) -> Optional[Dict]:
        """
        Fetch the latest release entry from the CHANGELOG.md HTML page.
        """
        print(f"\n🔍 Fetching latest release from {self.name}...")
        print(f"   URL: {self.url}")

        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(self.url, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'lxml')
            article = soup.find('article', class_='markdown-body') or soup.find('div', class_='markdown-body')
            if not article:
                print("   ⚠️  No markdown-body found")
                return None

            latest_h2 = article.find('h2')
            if not latest_h2:
                print("   ⚠️  No release headers (h2) found")
                return None

            version = latest_h2.get_text(strip=True)

            # Find the parent of latest_h2 that is a direct child of article
            h2_container = latest_h2
            if article:
                parent = latest_h2.parent
                while parent and parent != article:
                    h2_container = parent
                    parent = parent.parent

            # Construct temp div for description elements
            temp_div = soup.new_tag('div')
            for sibling in h2_container.next_siblings:
                if sibling.name:
                    # If sibling is or contains h2, stop
                    if sibling.name == 'h2' or sibling.find('h2'):
                        break
                    import copy
                    temp_div.append(copy.copy(sibling))

            description = self._extract_description(temp_div)

            # Build release URL (use the anchor id if available)
            anchor = h2_container.find('a', class_='anchor')
            if anchor and anchor.get('href'):
                release_url = f"https://github.com/google-antigravity/antigravity-cli/blob/main/CHANGELOG.md{anchor.get('href')}"
            else:
                release_url = self.url

            # Format date: since CHANGELOG doesn't have a date, we leave it empty
            date = ""

            release_info = {
                'version': version,
                'url': release_url,
                'date': date,
                'description': description
            }

            print(f"   ✅ Found latest release: {version}")
            print(f"      URL: {release_url}")
            return release_info

        except Exception as e:
            print(f"   ❌ Error fetching releases: {e}")
            import traceback
            traceback.print_exc()
            return None
