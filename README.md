# AI Release Notifier 🤖

這是一個自動化的 GitHub Release 監控與通知工具，專門追蹤熱門 AI CLI 工具（如 Gemini, Copilot, Codex）的更新資訊。它會自動抓取最新版本、利用 Gemini AI 翻譯，並發送美化後的訊息到 Discord 頻道。

## ✨ 特色功能

- **可擴充架構**：採用 **Factory Pattern**，只需繼承 `BaseScraper` 並實作特定規則，即可輕鬆新增追蹤專案。
- **多專案追蹤**：預設支援 Gemini CLI, Copilot CLI 與 OpenAI Codex。
- **精準解析**：自動提取 New Features、Bug Fixes 等重要分類，並排除過於冗長的 Changelog 區塊，保留 Markdown 結構。
- **多語系翻譯**：支援透過環境變數自定義目標語言（預設為繁體中文），使用 Gemini 2.0 Flash 模型進行翻譯，保留原始格式。
- **Discord 整合**：支援長訊息自動分段（2000 字元限制）與錯誤處理。
- **版本追蹤**：透過 `last_versions.json` 記錄已處理的版本，避免重複通知。

## 🛠️ 技術棧

- **Python 3.12+**
- **uv** (現代化 Python 套件管理器)
- **BeautifulSoup4 & lxml** (網頁抓取)
- **Google GenAI** (Gemini 2.0 翻譯)
- **Pytest** (完整單元測試)

## 🚀 快速開始

### 1. 環境準備

確保您的系統已安裝 [uv](https://github.com/astral-sh/uv)。

### 2. 安裝依賴

```bash
uv sync
```

### 3. 設定環境變數

在專案根目錄建立 `.env` 檔案（可參考 `.env.example`）：

```env
DISCORD_WEBHOOK_URL="您的 Discord Webhook 網址"
GEMINI_API_KEY="您的 Gemini API 金鑰"
TRANSLATE_LANGUAGE="Traditional Chinese"
```
*註：程式會強制優先使用 `.env` 中的設定以避免系統舊有環境變數干擾。*

### 4. 執行程式

```bash
uv run python main.py
```

## 🧪 執行測試

本專案包含完整測試，涵蓋各類 Release 格式解析邏輯。

```bash
uv run -m pytest
```

## 📂 檔案結構

- `main.py`: 程式進入點，協調整體流程。
- `scrapers/`: 抓取邏輯目錄（Factory Pattern 實作）。
    - `base.py`: 定義 `BaseScraper` 抽象介面與通用抓取核心。
    - `factory.py`: `ScraperFactory` 負責根據 Key 產生對應實體。
    - `gemini.py`, `copilot.py`, `codex.py`: 具體的專案設定與抓取規則。
- `tests/`: 單元測試目錄。
- `.env`: 機密與語系設定檔（已加入 .gitignore）。
- `.env.example`: 環境變數設定範例。
- `last_versions.json`: 儲存最後一次抓取的版本號（自動生成）。
- `pyproject.toml`: 專案設定與依賴管理。
