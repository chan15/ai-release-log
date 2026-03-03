from typing import Optional, Dict

import requests
from bs4 import BeautifulSoup


class BaseScraper:
    """
    Base class for GitHub release scrapers.
    """

    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url

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
                pre_release_badge = section.find('span', class_='Label--warning')

                if pre_release_badge:
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
                release_url = ""
                if version_elem and version_elem.get('href'):
                    href = version_elem.get('href')
                    # Make it a full URL if it's a relative path
                    if href.startswith('/'):
                        release_url = f"https://github.com{href}"
                    else:
                        release_url = href

                # Extract date from relative-time element
                date_elem = section.find('relative-time')
                date = date_elem.get('datetime', '') if date_elem else ""

                # Extract description from markdown-body, preserving formatting and structure
                desc_elem = section.find('div', class_='markdown-body')
                description = ""
                if desc_elem:
                    # Replace code tags with backticks to preserve inline code
                    for code in desc_elem.find_all('code'):
                        code_text = code.get_text()
                        code.replace_with(f'`{code_text}`')

                    # Process elements in order to preserve structure
                    lines = []
                    skip_section = False
                    for elem in desc_elem.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol']):
                        if elem.name.startswith('h'):
                            header_text = elem.get_text(strip=True)
                            # Skip Changelog sections
                            if "changelog" in header_text.lower():
                                skip_section = True
                                continue
                            else:
                                skip_section = False

                            # Convert headers to markdown format (using at most 4 # for Discord visibility)
                            level = min(int(elem.name[1]), 4)
                            lines.append(f"\n{'#' * level} {header_text}")

                        if skip_section:
                            continue

                        if elem.name == 'p':
                            text = elem.get_text(strip=True)
                            if text:
                                lines.append(text)
                        elif elem.name in ['ul', 'ol']:
                            for li in elem.find_all('li', recursive=False):
                                # Remove nested list text from parent LI to avoid duplication
                                li_text = ""
                                for child in li.children:
                                    if child.name not in ['ul', 'ol']:
                                        li_text += child.get_text(strip=True)

                                if li_text:
                                    lines.append(f"- {li_text}")

                                # Handle nested lists if any
                                nested_list = li.find(['ul', 'ol'], recursive=False)
                                if nested_list:
                                    for n_li in nested_list.find_all('li', recursive=False):
                                        n_text = n_li.get_text(strip=True)
                                        if n_text:
                                            lines.append(f"  - {n_text}")

                    if lines:
                        description = '\n'.join(lines).strip()
                    else:
                        # Fallback
                        description = ' '.join(desc_elem.get_text().split())

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
