import pytest

import main as main_module
from main import (load_last_versions, save_last_versions, format_release_message, send_to_discord)
from scrapers import ScraperFactory, BaseScraper


@pytest.fixture
def temp_version_file(tmp_path, mocker):
    """Fixture to mock VERSION_FILE to a temporary path."""
    temp_file = tmp_path / "test_versions.json"
    mocker.patch("main.VERSION_FILE", temp_file)
    return temp_file


def test_load_last_versions_empty(temp_version_file):
    """Test loading versions when file doesn't exist."""
    versions = load_last_versions()
    assert all(v is None for v in versions.values())
    assert set(versions.keys()) == set(ScraperFactory.get_all_keys())


def test_save_and_load_versions(temp_version_file):
    """Test saving and then loading versions."""
    project_keys = ScraperFactory.get_all_keys()
    test_data = {key: f"v{i}.0.0" for i, key in enumerate(project_keys)}
    save_last_versions(test_data)

    loaded = load_last_versions()
    assert loaded == test_data


def test_format_release_message():
    """Test Discord message formatting."""
    release = {"version": "v1.2.3", "url": "https://example.com", "date": "2024-01-01", "description": "Fixed bugs"}
    msg = format_release_message("Test Project", release, translated=True)

    assert "🇹🇼" in msg
    assert "Test Project" in msg
    assert "v1.2.3" in msg
    assert "https://example.com" in msg
    assert "Fixed bugs" in msg


def test_fetch_latest_release_parsing(mocker):
    """Test parsing logic of BaseScraper with mocked HTML."""
    mock_html = """
    <div class="Box-body">
        <a class="Link--primary" href="/owner/repo/releases/tag/v1.1.0">v1.1.0</a>
        <relative-time datetime="2024-01-01T00:00:00Z"></relative-time>
        <div class="markdown-body">
            <h3>New Features</h3>
            <ul><li>Cool feature</li></ul>
            <h3>Changelog</h3>
            <ul><li>Internal change</li></ul>
        </div>
    </div>
    """

    mock_resp = mocker.Mock()
    mock_resp.content = mock_html.encode('utf-8')
    mock_resp.raise_for_status = mocker.Mock()
    mocker.patch("requests.get", return_value=mock_resp)

    scraper = BaseScraper("Test Project", "http://fake.url")
    release = scraper.fetch_latest_release()

    assert release["version"] == "v1.1.0"
    assert "### New Features" in release["description"]
    assert "- Cool feature" in release["description"]
    # Changelog should be skipped
    assert "Changelog" not in release["description"]
    assert "Internal change" not in release["description"]


def test_fetch_latest_release_skips_pre_release(mocker):
    """Test that pre-releases are skipped."""
    mock_html = """
    <div class="Box-body">
        <span class="Label--warning">Pre-release</span>
        <a class="Link--primary" href="/owner/repo/releases/tag/v2.0.0-beta">v2.0.0-beta</a>
    </div>
    <div class="Box-body">
        <a class="Link--primary" href="/owner/repo/releases/tag/v1.0.0">v1.0.0</a>
    </div>
    """

    mock_resp = mocker.Mock()
    mock_resp.content = mock_html.encode('utf-8')
    mocker.patch("requests.get", return_value=mock_resp)

    scraper = BaseScraper("Test Project", "http://fake.url")
    release = scraper.fetch_latest_release()
    assert release["version"] == "v1.0.0"


def test_send_to_discord_success(mocker):
    """Test successful Discord notification."""
    mocker.patch("main.DISCORD_WEBHOOK_URL", "https://example.com/webhook")
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.raise_for_status = mocker.Mock()

    result = send_to_discord("Hello Discord")
    assert result is True
    assert mock_post.called


def test_send_to_discord_requires_webhook(mocker):
    """Test that missing webhook URLs fail fast without an HTTP call."""
    mocker.patch("main.DISCORD_WEBHOOK_URL", None)
    mock_post = mocker.patch("requests.post")

    result = send_to_discord("Hello Discord", webhook_url=None)

    assert result is False
    mock_post.assert_not_called()


def test_send_to_discord_long_message(mocker):
    """Test that long messages are split."""
    mocker.patch("main.DISCORD_WEBHOOK_URL", "https://example.com/webhook")
    mock_post = mocker.patch("requests.post")
    long_msg = "A" * 2500

    send_to_discord(long_msg)
    # Should be split into at least 2 messages
    assert mock_post.call_count >= 2


def test_main_does_not_mark_version_processed_when_discord_fails(mocker):
    """Test that failed notifications do not advance stored versions."""
    mocker.patch("main.DISCORD_WEBHOOK_URL", "https://example.com/webhook")
    mocker.patch("main.GEMINI_API_KEY", None)
    mocker.patch("main.load_last_versions", return_value={"gemini": None})
    mocker.patch("main.save_last_versions")
    mocker.patch("main.send_to_discord", return_value=False)
    mocker.patch.object(ScraperFactory, "get_all_keys", return_value=["gemini"])

    scraper = mocker.Mock()
    scraper.name = "Gemini CLI"
    scraper.fetch_latest_release.return_value = {
        "version": "v1.0.0",
        "url": "https://example.com/release",
        "date": "2024-01-01",
        "description": "Notes",
    }
    mocker.patch.object(ScraperFactory, "get_scraper", return_value=scraper)

    main_module.main()
    main_module.save_last_versions.assert_not_called()


def test_fetch_gemini_style(mocker):
    """Test Gemini style with many pre-releases (nightly/preview)."""
    mock_html = """
    <div class="Box-body">
        <span class="Label--warning">Pre-release</span>
        <a class="Link--primary">v0.33.0-nightly</a>
    </div>
    <div class="Box-body">
        <span class="Label--warning">Pre-release</span>
        <a class="Link--primary">v0.32.0-preview</a>
    </div>
    <div class="Box-body">
        <a class="Link--primary" href="/tag/v0.31.0">v0.31.0</a>
        <div class="markdown-body"><p>Stable release</p></div>
    </div>
    """
    mocker.patch("requests.get", return_value=mocker.Mock(content=mock_html.encode(), raise_for_status=lambda: None))
    scraper = ScraperFactory.get_scraper("gemini")
    release = scraper.fetch_latest_release()
    assert release["version"] == "v0.31.0"


def test_fetch_latest_release_ignores_non_prerelease_warning_badge(mocker):
    """Test that warning badges without 'Pre-release' do not skip a release."""
    mock_html = """
    <div class="Box-body">
        <span class="Label--warning">Latest</span>
        <a class="Link--primary" href="/owner/repo/releases/tag/v1.2.0">v1.2.0</a>
        <div class="markdown-body"><p>Stable release</p></div>
    </div>
    """

    mock_resp = mocker.Mock()
    mock_resp.content = mock_html.encode('utf-8')
    mock_resp.raise_for_status = mocker.Mock()
    mocker.patch("requests.get", return_value=mock_resp)

    scraper = BaseScraper("Test Project", "http://fake.url")
    release = scraper.fetch_latest_release()

    assert release["version"] == "v1.2.0"


def test_fetch_latest_release_nested_lists_not_duplicated(mocker):
    """Test that nested list items are included once."""
    mock_html = """
    <div class="Box-body">
        <a class="Link--primary" href="/owner/repo/releases/tag/v1.1.0">v1.1.0</a>
        <div class="markdown-body">
            <ul>
                <li>Parent item
                    <ul><li>Nested item</li></ul>
                </li>
            </ul>
        </div>
    </div>
    """

    mock_resp = mocker.Mock()
    mock_resp.content = mock_html.encode('utf-8')
    mock_resp.raise_for_status = mocker.Mock()
    mocker.patch("requests.get", return_value=mock_resp)

    scraper = BaseScraper("Test Project", "http://fake.url")
    release = scraper.fetch_latest_release()

    assert release["description"].count("- Parent item") == 1
    assert release["description"].count("  - Nested item") == 1


def test_fetch_copilot_style(mocker):
    """Test Copilot style with simple numerical versions."""
    mock_html = """
    <div class="Box-body">
        <a class="Link--primary" href="/tag/0.0.420">0.0.420</a>
        <div class="markdown-body"><p>Simple update</p></div>
    </div>
    """
    mocker.patch("requests.get", return_value=mocker.Mock(content=mock_html.encode(), raise_for_status=lambda: None))
    scraper = ScraperFactory.get_scraper("copilot")
    release = scraper.fetch_latest_release()
    assert release["version"] == "0.0.420"


def test_fetch_codex_style(mocker):
    """Test Codex style with complex categories and Changelog to skip."""
    mock_html = """
    <div class="Box-body">
        <a class="Link--primary" href="/tag/rust-v0.107.0">0.107.0</a>
        <div class="markdown-body">
            <h2>New Features</h2>
            <ul><li>Support for new API</li></ul>
            <h2>Bug Fixes</h2>
            <ul><li>Fixed memory leak</li></ul>
            <h2>Changelog</h2>
            <p>This should be ignored</p>
            <ul><li>Internal refactor</li></ul>
            <h2>Documentation</h2>
            <p>Updated README</p>
        </div>
    </div>
    """
    mocker.patch("requests.get", return_value=mocker.Mock(content=mock_html.encode(), raise_for_status=lambda: None))
    scraper = ScraperFactory.get_scraper("codex")
    release = scraper.fetch_latest_release()

    desc = release["description"]
    assert "## New Features" in desc
    assert "- Support for new API" in desc
    assert "## Bug Fixes" in desc
    assert "- Fixed memory leak" in desc
    assert "## Documentation" in desc
    assert "Updated README" in desc

    # Verify Changelog exclusion
    assert "Changelog" not in desc
    assert "Internal refactor" not in desc
    assert "This should be ignored" not in desc
