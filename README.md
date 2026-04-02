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

- **Python 3.12+**（最低需求版本）
- **uv**（現代化 Python 套件管理器）

  | 操作 | 指令 |
  |------|------|
  | 安裝依賴 | `uv sync` |
  | 新增套件 | `uv add <package>` |
  | 執行程式 | `uv run main.py` |
  | 執行測試 | `uv run -m pytest` |

- **BeautifulSoup4 & lxml**（網頁抓取）
- **Google GenAI**（Gemini 2.0 翻譯）
- **Pytest + pytest-mock**（完整單元測試）

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
*註：程式會強制優先使用 `.env` 中的設定以避免系統舊有環境變數干擾。敏感資訊（Webhook、API Key）與語言設定均須存放於此，嚴禁硬編碼於程式碼中。*

### 4. 執行程式

```bash
uv run main.py
```

#### 指定要執行的 vendor（可多個）

若有帶參數，程式只會執行指定的爬蟲；參數不分大小寫，且重複項目會自動忽略。

```bash
uv run main.py copilot gemini
uv run main.py CoPiLoT GEMINI
```

若其中任一參數無效，程式會直接停止（exit code 1），並顯示支援清單：

```bash
uv run main.py copilot unknown
# ❌ Unsupported vendor(s): unknown
#    Supported vendors: gemini, copilot, codex
```

## 🧪 執行測試

本專案使用 `pytest` 與 `pytest-mock`，涵蓋以下驗證範圍：

- 版本檔案讀取/儲存邏輯
- 不同發布風格的解析邏輯（Gemini、Copilot、Codex）
- Pre-release 過濾與 Changelog 排除行為
- Discord 2000 字元分段邏輯
- Vendor 參數解析（大小寫、去重、無效參數中止）

```bash
uv run -m pytest
```

## 📜 開發規範

本節定義程式碼標準，所有修改與擴充須嚴格遵守。

### GitHub 抓取（Scraping）

- **結構保留**：解析 GitHub Release 時，必須保留標題層級（`#`）與清單結構。
- **過濾規則**：
    - 自動跳過帶有 `Label--warning` 標記的 Pre-release。
    - 自動偵測並跳過標題包含 `Changelog`（不分大小寫）的區塊。
- **內容處理**：Inline code（`<code>`）必須轉換為 Markdown 反引號格式。

### 翻譯（Translation）

- **Prompt 語言**：翻譯 Prompt 必須使用英文，以確保模型穩定輸出。
- **動態語言**：目標翻譯語言須從環境變數 `TRANSLATE_LANGUAGE` 讀取。
- **純淨輸出**：要求模型僅回傳翻譯內容，不得包含前言或額外說明。

## 📂 檔案結構

- `main.py`：程式進入點，協調整體流程。
- `scrapers/`：抓取邏輯目錄（Factory Pattern 實作）。
    - `base.py`：定義 `BaseScraper` 抽象介面與通用抓取核心。
    - `factory.py`：`ScraperFactory` 負責根據 Key 產生對應實體。
    - `gemini.py`, `copilot.py`, `codex.py`：具體的專案設定與抓取規則。
- `tests/`：單元測試目錄。
- `.env`：機密與語系設定檔（**已加入 `.gitignore`**，請勿提交）。
- `.env.example`：環境變數設定範例。
- `last_versions.json`：儲存最後一次抓取的版本號（自動生成，**已加入 `.gitignore`**）。
- `pyproject.toml`：專案設定與依賴管理。
