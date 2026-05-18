# Session Lens

從 Claude Code / Codex 的 session 資料中提取有用的對話內容。過濾掉約 97% 的雜訊（系統提示、工具呼叫、思考區塊等），只保留用戶訊息和助手回覆。

附帶一個網頁介面，可以瀏覽、篩選、展開查看所有 session。

## 快速開始

```bash
# 1. 複製設定檔
cp config.example.json config.json

# 2. 編輯 config.json（見下方說明）

# 3. 處理所有 session 並開瀏覽器
python3 digest.py --serve
```

## 設定

編輯 `config.json`：

```json
{
  "claude_dir": "~/.claude",
  "codex_dir": "~/.codex",
  "categories": {
    "工作": ["my-company", "work-project"],
    "Side Project": ["side-project"],
    "學習": ["tutorial", "learning"]
  },
  "default_category": "其他",
  "port": 8919
}
```

| 欄位 | 說明 |
|------|------|
| `claude_dir` | Claude Code 的資料目錄，預設 `~/.claude` |
| `codex_dir` | Codex 的資料目錄，預設 `~/.codex`。設成 `null` 可關閉 Codex session 掃描 |
| `categories` | 分類規則。key 是分類名稱，value 是專案路徑中要比對的關鍵字列表 |
| `default_category` | 不符合任何規則時的預設分類 |
| `port` | 網頁介面的 HTTP server port |

比對邏輯：session 的專案路徑包含某個關鍵字，就歸到對應分類。第一個符合的規則生效。

## 指令

```bash
python3 digest.py              # 處理 session（增量，只處理新的或有變動的）
python3 digest.py --serve      # 處理 + 啟動網頁介面
python3 digest.py --force      # 忽略快取，重新處理所有 session
python3 digest.py --port 3000  # 指定 port
```

## 產出

執行後會在同目錄下產生（皆在 `.gitignore` 中）：

| 檔案 | 說明 |
|------|------|
| `index.json` | 所有 session 的索引 |
| `sessions/*.json` | 每個 session 過濾後的對話內容。Claude session 使用原始 UUID；Codex session 使用 `codex-<uuid>` |
| `.state.json` | 增量處理的快取狀態 |

## 搭配 Claude Code 使用

開一個新的 Claude Code session，讓它讀索引來掌握你的工作進度：

```
先跑 python3 ~/Desktop/session-lens/digest.py
然後讀 ~/Desktop/session-lens/index.json，告訴我最近三天在忙什麼
```

看到想 resume 的 session：

```bash
claude --resume <session-id>
```

## 無外部依賴

純 Python 標準庫，不需要 pip install。前端是純 HTML + JS，不需要 Node.js。
