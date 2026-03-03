import json
import os
from pathlib import Path
from typing import Dict, Optional

import google.genai as genai
import requests
from dotenv import load_dotenv

from scrapers import ScraperFactory

# Load environment variables, overriding system variables if they exist in .env
load_dotenv(override=True)

# Discord webhook URL
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

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
    project_keys = ScraperFactory.get_all_keys()
    if VERSION_FILE.exists():
        try:
            with open(VERSION_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading version file: {e}")
            return {key: None for key in project_keys}
    return {key: None for key in project_keys}


def save_last_versions(versions: Dict[str, Optional[str]]) -> None:
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


def send_to_discord(content: str, webhook_url: Optional[str] = DISCORD_WEBHOOK_URL) -> bool:
    """
    Send message to Discord via webhook.

    Args:
        content: Message content to send
        webhook_url: Discord webhook URL
    """
    if not webhook_url:
        print("   ⚠️  Discord webhook URL is not configured")
        return False

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
    print("GitHub Release Scraper with Gemini Translation (Factory Pattern)")
    print("=" * 60)

    # Load last processed versions
    print("\n📋 Loading last processed versions...")
    last_versions = load_last_versions()
    print(f"   Last versions: {json.dumps(last_versions, indent=2, ensure_ascii=False)}")

    # API key
    api_key = GEMINI_API_KEY

    # Track new versions
    new_versions = {}
    has_updates = False

    # Process each project key
    for project_key in ScraperFactory.get_all_keys():
        # Get scraper from factory
        scraper = ScraperFactory.get_scraper(project_key)
        if not scraper:
            continue

        project_name = scraper.name

        print(f"\n{'=' * 60}")
        print(f"Processing {project_name}")
        print(f"{'=' * 60}")

        # Fetch latest release
        latest_release = scraper.fetch_latest_release()

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
        # Translate the release
        print(f"\n🌐 Translating {project_name} release...")
        translated_release = latest_release.copy()

        if latest_release['description'] and api_key:
            translated_release['description'] = translate_with_gemini(latest_release['description'], api_key)

        message = format_release_message(project_name, translated_release, translated=bool(api_key))

        # Send to Discord
        notification_sent = True
        if DISCORD_WEBHOOK_URL:
            print(f"\n📤 Sending {project_name} update to Discord...")
            notification_sent = send_to_discord(message)
        else:
            print(f"\n⚠️  DISCORD_WEBHOOK_URL not set, skipping Discord notification.")
            print(f"Formatted message (first 100 chars): {message[:100]}...")

        if notification_sent:
            has_updates = True
            new_versions[project_key] = current_version
        else:
            print(f"   ⚠️  Notification failed, keeping last processed version at {last_version or 'None'}")
            new_versions[project_key] = last_version

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
