import json
import os
from pathlib import Path
from typing import Dict, Optional

import google.genai as genai
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Discord webhook URL
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# GitHub release URLs
REPOS = {"gemini": "https://github.com/google-gemini/gemini-cli/releases",
         "copilot": "https://github.com/github/copilot-cli/releases",
         "codex": "https://github.com/openai/codex/releases"}

# File to store last processed versions
VERSION_FILE = Path(__file__).parent / "last_versions.json"

# Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Target language for translation
TARGET_LANGUAGE = os.getenv("TRANSLATE_LANGUAGE", "Traditional Chinese")


def load_last_versions() -> Dict[str, Optional[str]]:
    """
    Load the last processed versions from file.

    Returns:
        Dictionary mapping project names to their last processed version
    """
    if VERSION_FILE.exists():
        try:
            with open(VERSION_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading version file: {e}")
            return {key: None for key in REPOS.keys()}
    return {key: None for key in REPOS.keys()}


def save_last_versions(versions: Dict[str, Optional[str]]):
    """
    Save the last processed versions to file.

    Args:
        versions: Dictionary mapping project names to their last processed version
    """
    try:
        with open(VERSION_FILE, 'w', encoding='utf-8') as f:
            json.dump(versions, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved last versions to {VERSION_FILE}")
    except Exception as e:
        print(f"⚠️  Error saving version file: {e}")


def fetch_latest_release(url: str, project_name: str) -> Optional[Dict]:
    """
    Fetch the latest non-pre-release from GitHub release page.

    Args:
        url: GitHub releases page URL
        project_name: Name of the project for logging

    Returns:
        Dictionary containing version, date, and description of the latest release, or None if not found
    """
    print(f"\n🔍 Fetching latest release from {project_name}...")
    print(f"   URL: {url}")

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=30)
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
                            # (BeautifulSoup's get_text() includes children's text)
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


def translate_with_gemini(text: str, api_key: str) -> str:
    """
    Translate text to the target language using Gemini API.

    Args:
        text: Text to translate
        api_key: Gemini API key

    Returns:
        Translated text in target language
    """
    try:
        client = genai.Client(api_key=api_key)

        prompt = f"""Translate the following content into {TARGET_LANGUAGE}. 
Maintain the original Markdown formatting, structure, headers, and code blocks exactly.

Content to translate:
{text}

Return ONLY the translated content without any extra explanation or preamble."""

        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        return response.text

    except Exception as e:
        print(f"   ⚠️  Translation error: {e}")
        return text  # Return original text if translation fails


def send_to_discord(content: str, webhook_url: str = DISCORD_WEBHOOK_URL):
    """
    Send message to Discord via webhook.

    Args:
        content: Message content to send
        webhook_url: Discord webhook URL
    """
    print(f"\n📤 Sending to Discord...")

    try:
        # Split content if it's too long (Discord limit is 2000 characters)
        max_length = 2000
        if len(content) <= max_length:
            messages = [content]
        else:
            # Split into chunks
            messages = []
            while content:
                if len(content) <= max_length:
                    messages.append(content)
                    break
                # Find a good split point (newline)
                split_point = content[:max_length].rfind('\n')
                if split_point == -1:
                    split_point = max_length
                messages.append(content[:split_point])
                content = content[split_point:].lstrip()

        # Send each message
        for i, msg in enumerate(messages):
            payload = {"content": msg}
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            print(f"   ✅ Message {i + 1}/{len(messages)} sent successfully")

        return True

    except Exception as e:
        print(f"   ❌ Error sending to Discord: {e}")
        return False


def format_release_message(project_name: str, release: Dict, translated: bool = False) -> str:
    """
    Format release information into a Discord message.

    Args:
        project_name: Name of the project
        release: Release dictionary
        translated: Whether the content has been translated

    Returns:
        Formatted message string
    """
    lang_flag = "🇹🇼" if translated else "🇺🇸"
    message = f"## {lang_flag} {project_name} - Latest Release\n\n"

    # Add release URL at the top
    if release.get('url'):
        message += f"🔗 **Release Link**: {release['url']}\n\n"

    message += f"### {release['version']}\n"
    if release['date']:
        message += f"📅 {release['date']}\n"
    if release['description']:
        message += f"\n{release['description']}\n"

    return message


def main():
    """Main function to orchestrate the release scraping, translation, and Discord notification."""

    print("=" * 60)
    print("GitHub Release Scraper with Gemini Translation")
    print("=" * 60)

    # Load last processed versions
    print("\n📋 Loading last processed versions...")
    last_versions = load_last_versions()
    print(f"   Last versions: {json.dumps(last_versions, indent=2, ensure_ascii=False)}")

    # Use hardcoded API key
    print("\n📋 Using Gemini API for translation...")
    api_key = GEMINI_API_KEY

    # Track new versions
    new_versions = {}
    has_updates = False

    # Process each repository
    for project_key, repo_url in REPOS.items():
        project_name = f"{project_key.capitalize()} CLI"

        print(f"\n{'=' * 60}")
        print(f"Processing {project_name}")
        print(f"{'=' * 60}")

        # Fetch latest release
        latest_release = fetch_latest_release(repo_url, project_name)

        if not latest_release:
            print(f"   ⚠️  No release found for {project_name}")
            new_versions[project_key] = last_versions.get(project_key)
            continue

        current_version = latest_release['version']
        last_version = last_versions.get(project_key)

        # Check if this is a new version
        if current_version == last_version:
            print(f"   ℹ️  No new release - current version {current_version} already processed")
            new_versions[project_key] = current_version
            continue

        # New version found!
        print(f"   🆕 New release detected!")
        print(f"      Last processed: {last_version or 'None'}")
        print(f"      Current: {current_version}")
        has_updates = True
        new_versions[project_key] = current_version

        # Translate the release
        print(f"\n🌐 Translating {project_name} release...")
        translated_release = latest_release.copy()

        if latest_release['description']:
            translated_release['description'] = translate_with_gemini(latest_release['description'], api_key)

        message = format_release_message(project_name, translated_release, translated=True)

        # Send to Discord
        print(f"\n📤 Sending {project_name} update to Discord...")
        send_to_discord(message)

    # Save the new versions
    if has_updates:
        print(f"\n{'=' * 60}")
        print("💾 Saving updated version information...")
        save_last_versions(new_versions)
        print(f"   New versions: {json.dumps(new_versions, indent=2, ensure_ascii=False)}")
    else:
        print(f"\n{'=' * 60}")
        print("ℹ️  No new releases found - nothing to update")

    print("\n" + "=" * 60)
    print("✅ Process completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
