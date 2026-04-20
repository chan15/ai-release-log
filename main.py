import json
import os
import sys
import time
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
TRANSLATION_MODEL = os.getenv("GEMINI_TRANSLATION_MODEL", "gemini-2.5-flash")
TRANSLATION_MAX_RETRIES = 3
TRANSLATION_RETRY_DELAY_SECONDS = 1.0


def resolve_target_project_keys(vendor_args: list[str]) -> list[str]:
    """Resolve and validate target project keys from CLI vendor arguments."""
    available_keys = ScraperFactory.get_all_keys()

    # Show usage when the user explicitly asks for help.
    if any(arg in ("-h", "--help") for arg in vendor_args):
        print(f"Usage: main.py [vendor ...]\n   Supported vendors: {', '.join(available_keys)}")
        raise SystemExit(0)

    # No vendor args means process all supported scrapers.
    if not vendor_args:
        return available_keys

    available_lookup = {key.lower(): key for key in available_keys}
    selected_keys = []
    seen = set()
    invalid_vendors = []

    for vendor in vendor_args:
        normalized_vendor = vendor.lower()
        canonical_key = available_lookup.get(normalized_vendor)
        if not canonical_key:
            invalid_vendors.append(vendor)
            continue

        # Silently deduplicate repeated vendors.
        if canonical_key in seen:
            continue
        seen.add(canonical_key)
        selected_keys.append(canonical_key)

    if invalid_vendors:
        print(f"❌ Unsupported vendor(s): {', '.join(invalid_vendors)}")
        print(f"   Supported vendors: {', '.join(available_keys)}")
        raise SystemExit(1)

    return selected_keys


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
    except Exception as e:
        print(f"   ⚠️  Translation error: {e}")
        return text

    prompt = f"""Translate the following content into {TARGET_LANGUAGE}. 
Maintain the original Markdown formatting, structure, headers, and code blocks exactly.

Content to translate:
{text}

Return ONLY the translated content without any extra explanation or preamble."""
    for attempt in range(1, TRANSLATION_MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(model=TRANSLATION_MODEL, contents=prompt)
            translated_text = response.text
            if translated_text:
                return translated_text

            # Some Gemini responses have no `response.text` even though the request
            # itself succeeded, for example when candidates are empty or contain only
            # non-text parts.
            finish_reason = None
            if getattr(response, "candidates", None):
                finish_reason = getattr(response.candidates[0], "finish_reason", None)
            print(f"   ⚠️  Translation returned no text (finish_reason={finish_reason!r})")
            return text

        except Exception as e:
            error_message = str(e)
            is_retryable = any(
                marker in error_message
                for marker in ("429", "RESOURCE_EXHAUSTED", "Temporary failure in name resolution", "timed out")
            )
            if attempt < TRANSLATION_MAX_RETRIES and is_retryable:
                delay_seconds = TRANSLATION_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                print(
                    f"   ⚠️  Translation attempt {attempt}/{TRANSLATION_MAX_RETRIES} failed: {e}. "
                    f"Retrying in {delay_seconds:.1f}s..."
                )
                time.sleep(delay_seconds)
                continue

            print(f"   ⚠️  Translation error: {e}")
            return text  # Return original text if translation fails


def send_to_discord(content: str, webhook_url: Optional[str] = None) -> bool:
    """
    Send message to Discord via webhook.

    Args:
        content: Message content to send
        webhook_url: Discord webhook URL
    """
    if webhook_url is None:
        webhook_url = DISCORD_WEBHOOK_URL

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


def main(vendor_args: Optional[list[str]] = None):
    """Main function to orchestrate the release scraping, translation, and Discord notification."""

    if vendor_args is None:
        vendor_args = []

    target_project_keys = resolve_target_project_keys(vendor_args)

    print("=" * 60)
    print("GitHub Release Scraper with Gemini Translation (Factory Pattern)")
    print("=" * 60)

    if vendor_args:
        print(f"\n🎯 Target vendors: {', '.join(target_project_keys)}")

    # Load last processed versions
    print("\n📋 Loading last processed versions...")
    last_versions = load_last_versions()
    print(f"   Last versions: {json.dumps(last_versions, indent=2, ensure_ascii=False)}")

    # API key
    api_key = GEMINI_API_KEY

    # Track new versions
    new_versions = last_versions.copy()
    has_updates = False

    # Process each selected project key
    for project_key in target_project_keys:
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
            # new_versions already holds last_versions values from .copy(); no update needed.
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

        translation_applied = False
        if latest_release['description'] and api_key:
            translated_description = translate_with_gemini(latest_release['description'], api_key)
            translated_release['description'] = translated_description
            translation_applied = translated_description != latest_release['description']

        message = format_release_message(project_name, translated_release, translated=translation_applied)

        # Send to Discord
        notification_sent = True
        if DISCORD_WEBHOOK_URL:
            print(f"\n📤 Sending {project_name} update to Discord...")
            notification_sent = send_to_discord(message)
        else:
            # No webhook configured: treat as "sent" so the version is still saved.
            # If a webhook is added later, this release will NOT be re-sent.
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


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
