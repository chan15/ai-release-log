# AI Release Notifier 🤖

這是一個自動化的 GitHub Release 監控與通知工具，專門追蹤熱門 AI CLI 工具（如 Gemini, Copilot, Codex）的更新資訊。它會自動抓取最新版本、利用 Gemini AI 翻譯，並發送美化後的訊息到 Discord 頻道。

## ✨ 特色功能

- **多專案追蹤**：預設支援 Gemini CLI, Copilot CLI 與 OpenAI Codex。
- **精準解析**：自動提取 New Features、Bug Fixes 等重要分類，並排除過於冗長的 Changelog 區塊。
- **多語系翻譯**：支援透過環境變數自定義目標語言（預設為繁體中文），使用 Gemini 2.0 Flash 模型進行翻譯，保留原始的 Markdown 格式。
- **Discord 整合**：支援長訊息自動分段，確保符合 Discord 的 2000 字元限制。
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

在專案根目錄建立 `.env` 檔案，內容如下：

```env
DISCORD_WEBHOOK_URL="您的 Discord Webhook 網址"
GEMINI_API_KEY="您的 Gemini API 金鑰"
TRANSLATE_LANGUAGE="Traditional Chinese"
```

### 4. 執行程式

```bash
uv run python main.py
```

## 🧪 執行測試

本專案包含 10 個測試案例，涵蓋了各種不同的 GitHub Release 格式解析與翻譯 Prompt 邏輯。

## 📂 檔案結構

- `main.py`: 核心執行邏輯。
- `tests/`: 單元測試目錄。
- `.env`: 機密與語系設定檔（已加入 .gitignore）。
- `last_versions.json`: 儲存最後一次抓取的版本號。
- `pyproject.toml`: 專案設定與依賴管理。
