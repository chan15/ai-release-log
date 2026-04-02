from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


class BaseScraper:
    """
    Base class for GitHub release scrapers.
    """

    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url

    def _is_pre_release(self, section: Tag) -> bool:
        """Return True when GitHub explicitly labels a release as pre-release."""
        for badge in section.find_all('span', class_='Label--warning'):
            badge_text = badge.get_text(" ", strip=True).lower()
            if "pre-release" in badge_text:
                return True
        return False

    def _build_release_url(self, version_elem: Optional[Tag]) -> str:
        """Normalize a release link into a fully-qualified GitHub URL."""
        if not version_elem or not version_elem.get('href'):
            return ""

        href = version_elem.get('href')
        if href.startswith('/'):
            return f"https://github.com{href}"
        return href

    def _extract_list_item_text(self, item: Tag) -> str:
        """Extract only the direct text for a list item, excluding nested lists."""
        parts = []
        for child in item.contents:
            if isinstance(child, NavigableString):
                text = str(child).strip()
            elif getattr(child, 'name', None) in ['ul', 'ol']:
                continue
            else:
                text = child.get_text(" ", strip=True)

            if text:
                parts.append(text)

        return ' '.join(parts)

    def _append_list_items(self, lines: list[str], list_elem: Tag, indent: int = 0) -> None:
        """Flatten nested HTML lists into indented Markdown bullet points."""
        prefix = " " * indent
        for li in list_elem.find_all('li', recursive=False):
            item_text = self._extract_list_item_text(li)
            if item_text:
                lines.append(f"{prefix}- {item_text}")

            for nested_list in li.find_all(['ul', 'ol'], recursive=False):
                self._append_list_items(lines, nested_list, indent=indent + 2)

    def _extract_description(self, desc_elem: Optional[Tag]) -> str:
        """Convert GitHub release HTML into Discord-friendly Markdown."""
        if not desc_elem:
            return ""

        for code in desc_elem.find_all('code'):
            code_text = code.get_text()
            code.replace_with(f'`{code_text}`')

        lines = []
        skip_section = False
        for elem in desc_elem.find_all(recursive=False):
            if not isinstance(elem, Tag):  # pragma: no cover
                continue

            if elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                header_text = elem.get_text(" ", strip=True)
                if "changelog" in header_text.lower():
                    skip_section = True
                    continue

                skip_section = False
                level = min(int(elem.name[1]), 4)
                lines.append(f"\n{'#' * level} {header_text}")
                continue

            if skip_section:
                continue

            if elem.name == 'p':
                text = elem.get_text(" ", strip=True)
                if text:
                    lines.append(text)
            elif elem.name in ['ul', 'ol']:
                self._append_list_items(lines, elem)

        if lines:
            return '\n'.join(lines).strip()

        return ' '.join(desc_elem.get_text(" ", strip=True).split())

    def fetch_latest_release(self) -> Optional[Dict]:
        """
        Fetch the latest non-pre-release from GitHub release page.
        """
        print(f"\n🔍 Fetching latest release from {self.name}...")
        print(f"   URL: {self.url}")

        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(self.url, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'lxml')

            # Find all release sections - GitHub uses div.Box-body for each release
            release_sections = soup.find_all('div', class_='Box-body')

            print(f"   Found {len(release_sections)} release sections")

            # Find the first non-pre-release
            for section in release_sections:
                # Check if it's a pre-release - look for Label--warning with "Pre-release" text
                if self._is_pre_release(section):
                    # Extract version for logging
                    version_link = section.find('a', class_='Link--primary')
                    version_text = version_link.get_text(strip=True) if version_link else "Unknown"
                    print(f"   ⏭️  Skipping pre-release: {version_text}")
                    continue

                # Extract version/tag - it's in the Link--primary anchor
                version_elem = section.find('a', class_='Link--primary')
                if not version_elem:
                    # Try alternative: any link with /releases/tag/ in href
                    version_elem = section.find('a', href=lambda x: x and '/releases/tag/' in x)

                version = version_elem.get_text(strip=True) if version_elem else "Unknown"

                # Extract release URL
                release_url = self._build_release_url(version_elem)

                # Extract date from relative-time element
                date_elem = section.find('relative-time')
                date = date_elem.get('datetime', '') if date_elem else ""

                # Extract description from markdown-body, preserving formatting and structure
                desc_elem = section.find('div', class_='markdown-body')
                description = self._extract_description(desc_elem)

                release_info = {'version': version, 'url': release_url, 'date': date, 'description': description}

                print(f"   ✅ Found latest release: {version}")
                print(f"      URL: {release_url}")
                return release_info

            print(f"   ⚠️  No non-pre-release versions found")
            return None

        except Exception as e:
            print(f"   ❌ Error fetching releases: {e}")
            import traceback
            traceback.print_exc()
            return None
