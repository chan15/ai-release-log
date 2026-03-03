# Gemini Instructions: AI Release Notifier

本文件定義了此專案的開發規範與技術準則。所有後續的修改與擴充必須嚴格遵守以下規定。

## 🛠️ 技術棧規範

- **Python 版本**: 必須使用 Python 3.12 或更高版本。
- **套件管理**: 統一使用 `uv` 進行依賴管理與虛擬環境操作。
    - 新增套件：`uv add <package>`
    - 執行程式：`uv run python main.py`
    - 執行測試：`uv run -m pytest`
- **環境變數**: 敏感資訊（Webhook, API Key）與設定（語言）必須存放於 `.env` 中，嚴禁硬編碼。

## 📜 程式碼標準

### GitHub 抓取 (Scraping)
- **結構保留**: 解析 GitHub Release 時，必須保留標題級別（`#`）與清單結構。
- **過濾規則**: 
    - 自動跳過 `Label--warning` 標記的 Pre-release。
    - 自動偵測並跳過標題包含 "Changelog" (不分大小寫) 的區塊。
- **內容處理**: Inline code (`<code>`) 必須轉換為 Markdown 的反引號格式。

### 翻譯 (Translation)
- **Prompt 設計**: 翻譯 Prompt 必須使用英文，以確保模型的穩定輸出。
- **動態語言**: 翻譯目標語言必須從環境變數 `TRANSLATE_LANGUAGE` 讀取。
- **純淨輸出**: 要求模型僅回傳翻譯內容，不得包含前言或說明。

## 🧪 測試規範

- **測試框架**: 使用 `pytest` 與 `pytest-mock`。
- **驗證範圍**: 
    - 檔案讀取/儲存邏輯。
    - 不同發布風格的解析邏輯（Gemini, Copilot, Codex）。
    - 訊息分段處理邏輯（Discord 2000 字元限制）。

## 📂 檔案與路徑

- **狀態管理**: `last_versions.json` 存放於專案根目錄，用於追蹤進度，不應進入 Git。
- **文件管理**: `.env` 與 `last_versions.json` 必須在 `.gitignore` 的過濾名單中。
