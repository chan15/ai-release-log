import pytest

import main as main_module
from main import (
    load_last_versions,
    save_last_versions,
    format_release_message,
    send_to_discord,
    resolve_target_project_keys,
    translate_with_gemini,
)
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


def test_resolve_target_project_keys_no_args_returns_all(mocker):
    """Test that empty vendor_args returns all supported keys unchanged."""
    all_keys = ["gemini", "copilot", "codex"]
    mocker.patch.object(ScraperFactory, "get_all_keys", return_value=all_keys)

    selected = resolve_target_project_keys([])

    assert selected == all_keys


def test_resolve_target_project_keys_case_insensitive_and_dedup(mocker):
    """Test vendor parsing is case-insensitive and repeated vendors are deduplicated."""
    mocker.patch.object(ScraperFactory, "get_all_keys", return_value=["gemini", "copilot", "codex"])

    selected = resolve_target_project_keys(["COPILOT", "gemini", "CoPiLoT"])

    assert selected == ["copilot", "gemini"]


def test_resolve_target_project_keys_multiple_invalid_vendors_all_reported(mocker, capsys):
    """Test that all invalid vendors are reported together before failing."""
    mocker.patch.object(ScraperFactory, "get_all_keys", return_value=["gemini", "copilot", "codex"])

    with pytest.raises(SystemExit) as exc_info:
        resolve_target_project_keys(["gemini", "foo", "bar"])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "foo" in captured.out
    assert "bar" in captured.out


def test_main_runs_only_selected_vendors(mocker):
    """Test that passing vendors only runs selected scrapers."""
    mocker.patch.object(ScraperFactory, "get_all_keys", return_value=["gemini", "copilot", "codex"])
    mocker.patch("main.GEMINI_API_KEY", None)
    mocker.patch("main.DISCORD_WEBHOOK_URL", None)
    mocker.patch("main.load_last_versions", return_value={"gemini": None, "copilot": None, "codex": None})
    mock_save = mocker.patch("main.save_last_versions")

    gemini_scraper = mocker.Mock()
    gemini_scraper.name = "Gemini CLI"
    gemini_scraper.fetch_latest_release.return_value = {
        "version": "v1.0.0",
        "url": "https://example.com/gemini",
        "date": "2024-01-01",
        "description": "Gemini notes",
    }

    copilot_scraper = mocker.Mock()
    copilot_scraper.name = "Copilot CLI"
    copilot_scraper.fetch_latest_release.return_value = {
        "version": "v2.0.0",
        "url": "https://example.com/copilot",
        "date": "2024-01-02",
        "description": "Copilot notes",
    }

    def get_scraper_side_effect(project_key):
        return {"gemini": gemini_scraper, "copilot": copilot_scraper}.get(project_key)

    mock_get_scraper = mocker.patch.object(ScraperFactory, "get_scraper", side_effect=get_scraper_side_effect)

    main_module.main(["COPILOT", "gemini"])

    assert mock_get_scraper.call_args_list == [mocker.call("copilot"), mocker.call("gemini")]
    mock_save.assert_called_once_with({"gemini": "v1.0.0", "copilot": "v2.0.0", "codex": None})


def test_main_invalid_vendor_exits_without_processing(mocker):
    """Test that any unsupported vendor fails fast and stops execution."""
    mocker.patch.object(ScraperFactory, "get_all_keys", return_value=["gemini", "copilot", "codex"])
    mock_load = mocker.patch("main.load_last_versions")
    mock_get_scraper = mocker.patch.object(ScraperFactory, "get_scraper")

    with pytest.raises(SystemExit) as exc_info:
        main_module.main(["copilot", "unknown_vendor"])

    assert exc_info.value.code == 1
    mock_load.assert_not_called()
    mock_get_scraper.assert_not_called()


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


# ── resolve_target_project_keys ──────────────────────────────────────────────

def test_resolve_target_project_keys_help_flag(mocker, capsys):
    """Test that -h and --help display usage and exit 0."""
    mocker.patch.object(ScraperFactory, "get_all_keys", return_value=["gemini", "copilot", "codex"])
    for flag in ["-h", "--help"]:
        with pytest.raises(SystemExit) as exc_info:
            resolve_target_project_keys([flag])
        assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Usage" in captured.out
    assert "gemini" in captured.out


# ── translate_with_gemini ─────────────────────────────────────────────────────

def test_translate_with_gemini_success(mocker):
    """Test successful translation returns model response text."""
    mock_response = mocker.MagicMock()
    mock_response.text = "翻譯後的文字"
    mock_client = mocker.MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mocker.patch("main.genai.Client", return_value=mock_client)

    result = translate_with_gemini("Hello world", "fake-key")

    assert result == "翻譯後的文字"
    mock_client.models.generate_content.assert_called_once()


def test_translate_with_gemini_error(mocker):
    """Test that original text is returned when the API raises an error."""
    mocker.patch("main.genai.Client", side_effect=Exception("API error"))

    result = translate_with_gemini("Hello world", "fake-key")

    assert result == "Hello world"


# ── load_last_versions ────────────────────────────────────────────────────────

def test_load_last_versions_corrupted_file(temp_version_file):
    """Test that a corrupt JSON file falls back to an all-None dict."""
    temp_version_file.write_text("not valid json {{{")

    versions = load_last_versions()

    assert all(v is None for v in versions.values())


# ── save_last_versions ────────────────────────────────────────────────────────

def test_save_last_versions_write_error(mocker):
    """Test that a file write error is handled gracefully without raising."""
    mocker.patch("builtins.open", side_effect=OSError("disk full"))

    save_last_versions({"gemini": "v1.0.0"})  # must not raise


# ── send_to_discord ───────────────────────────────────────────────────────────

def test_send_to_discord_request_exception(mocker):
    """Test that a network error causes send_to_discord to return False."""
    mocker.patch("main.DISCORD_WEBHOOK_URL", "https://example.com/webhook")
    mocker.patch("requests.post", side_effect=Exception("Connection error"))

    result = send_to_discord("Hello Discord")

    assert result is False


# ── main() flow ───────────────────────────────────────────────────────────────

def test_main_skips_none_scraper(mocker):
    """Test that main() skips gracefully when get_scraper returns None."""
    mocker.patch.object(ScraperFactory, "get_all_keys", return_value=["gemini"])
    mocker.patch("main.load_last_versions", return_value={"gemini": None})
    mock_save = mocker.patch("main.save_last_versions")
    mocker.patch.object(ScraperFactory, "get_scraper", return_value=None)

    main_module.main()

    mock_save.assert_not_called()


def test_main_no_release_found(mocker):
    """Test that main() handles a scraper that returns no release."""
    mocker.patch.object(ScraperFactory, "get_all_keys", return_value=["gemini"])
    mocker.patch("main.load_last_versions", return_value={"gemini": None})
    mock_save = mocker.patch("main.save_last_versions")

    scraper = mocker.Mock()
    scraper.name = "Gemini CLI"
    scraper.fetch_latest_release.return_value = None
    mocker.patch.object(ScraperFactory, "get_scraper", return_value=scraper)

    main_module.main()

    mock_save.assert_not_called()


def test_main_version_already_processed(mocker):
    """Test that main() skips a release whose version was already processed."""
    mocker.patch.object(ScraperFactory, "get_all_keys", return_value=["gemini"])
    mocker.patch("main.load_last_versions", return_value={"gemini": "v1.0.0"})
    mock_save = mocker.patch("main.save_last_versions")

    scraper = mocker.Mock()
    scraper.name = "Gemini CLI"
    scraper.fetch_latest_release.return_value = {
        "version": "v1.0.0",
        "url": "https://example.com",
        "date": "2024-01-01",
        "description": "Notes",
    }
    mocker.patch.object(ScraperFactory, "get_scraper", return_value=scraper)

    main_module.main()

    mock_save.assert_not_called()


def test_main_translates_when_api_key_set(mocker):
    """Test that main() calls translate_with_gemini when GEMINI_API_KEY is present."""
    mocker.patch.object(ScraperFactory, "get_all_keys", return_value=["gemini"])
    mocker.patch("main.GEMINI_API_KEY", "fake-key")
    mocker.patch("main.DISCORD_WEBHOOK_URL", None)
    mocker.patch("main.load_last_versions", return_value={"gemini": None})
    mocker.patch("main.save_last_versions")
    mock_translate = mocker.patch("main.translate_with_gemini", return_value="翻譯內容")

    scraper = mocker.Mock()
    scraper.name = "Gemini CLI"
    scraper.fetch_latest_release.return_value = {
        "version": "v2.0.0",
        "url": "https://example.com",
        "date": "2024-01-01",
        "description": "Original notes",
    }
    mocker.patch.object(ScraperFactory, "get_scraper", return_value=scraper)

    main_module.main()

    mock_translate.assert_called_once_with("Original notes", "fake-key")


# ── ScraperFactory ────────────────────────────────────────────────────────────

def test_get_scraper_invalid_key():
    """Test that get_scraper returns None for an unknown key."""
    assert ScraperFactory.get_scraper("nonexistent_project") is None


# ── BaseScraper._build_release_url ────────────────────────────────────────────

def test_build_release_url_no_href(mocker):
    """Test _build_release_url returns '' for None and elements without href."""
    scraper = BaseScraper("Test", "http://test.url")

    assert scraper._build_release_url(None) == ""

    no_href_elem = mocker.Mock()
    no_href_elem.get.return_value = None
    assert scraper._build_release_url(no_href_elem) == ""


def test_build_release_url_absolute_url(mocker):
    """Test _build_release_url returns absolute URLs unchanged."""
    scraper = BaseScraper("Test", "http://test.url")
    elem = mocker.Mock()
    elem.get.return_value = "https://external.example.com/releases/tag/v1.0.0"

    result = scraper._build_release_url(elem)

    assert result == "https://external.example.com/releases/tag/v1.0.0"


# ── BaseScraper._extract_list_item_text ───────────────────────────────────────

def test_extract_list_item_with_inline_tag():
    """Test _extract_list_item_text with an inline Tag child (e.g. <strong>)."""
    from bs4 import BeautifulSoup

    scraper = BaseScraper("Test", "http://test.url")
    soup = BeautifulSoup("<li><strong>Bold</strong> feature text</li>", "lxml")
    li = soup.find("li")

    result = scraper._extract_list_item_text(li)

    assert "Bold" in result
    assert "feature text" in result


# ── BaseScraper._extract_description / fetch_latest_release ──────────────────

def test_extract_description_converts_inline_code(mocker):
    """Test that <code> tags inside release notes are converted to backticks."""
    mock_html = """
    <div class="Box-body">
        <a class="Link--primary" href="/tag/v1.0.0">v1.0.0</a>
        <div class="markdown-body">
            <p>Run <code>npm install</code> to set up.</p>
        </div>
    </div>
    """
    mocker.patch("requests.get", return_value=mocker.Mock(
        content=mock_html.encode(), raise_for_status=mocker.Mock()
    ))

    release = BaseScraper("Test", "http://test.url").fetch_latest_release()

    assert "`npm install`" in release["description"]


def test_extract_description_fallback_plain_text(mocker):
    """Test that unrecognised tags fall back to plain-text extraction (line 100)."""
    mock_html = """
    <div class="Box-body">
        <a class="Link--primary" href="/tag/v1.0.0">v1.0.0</a>
        <div class="markdown-body">
            <span>Unstructured plain text only</span>
        </div>
    </div>
    """
    mocker.patch("requests.get", return_value=mocker.Mock(
        content=mock_html.encode(), raise_for_status=mocker.Mock()
    ))

    release = BaseScraper("Test", "http://test.url").fetch_latest_release()

    assert release is not None
    assert "Unstructured plain text only" in release["description"]


def test_fetch_latest_release_alt_href(mocker):
    """Test version resolution via /releases/tag/ href when Link--primary is absent."""
    mock_html = """
    <div class="Box-body">
        <a href="/owner/repo/releases/tag/v3.0.0">Release v3.0.0</a>
        <div class="markdown-body"><p>Alt-href release notes.</p></div>
    </div>
    """
    mocker.patch("requests.get", return_value=mocker.Mock(
        content=mock_html.encode(), raise_for_status=mocker.Mock()
    ))

    release = BaseScraper("Test", "http://test.url").fetch_latest_release()

    assert release is not None
    assert release["url"] == "https://github.com/owner/repo/releases/tag/v3.0.0"


def test_fetch_latest_release_all_prerelease_returns_none(mocker):
    """Test that None is returned when every release section is a pre-release."""
    mock_html = """
    <div class="Box-body">
        <span class="Label--warning">Pre-release</span>
        <a class="Link--primary" href="/tag/v2.0.0-beta">v2.0.0-beta</a>
    </div>
    <div class="Box-body">
        <span class="Label--warning">Pre-release</span>
        <a class="Link--primary" href="/tag/v1.0.0-alpha">v1.0.0-alpha</a>
    </div>
    """
    mocker.patch("requests.get", return_value=mocker.Mock(
        content=mock_html.encode(), raise_for_status=mocker.Mock()
    ))

    release = BaseScraper("Test", "http://test.url").fetch_latest_release()

    assert release is None


def test_fetch_latest_release_network_exception(mocker):
    """Test that a network error returns None without raising."""
    mocker.patch("requests.get", side_effect=Exception("Network error"))

    release = BaseScraper("Test", "http://test.url").fetch_latest_release()

    assert release is None

