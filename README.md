# Session Lens

從 Claude Code / Codex 的 session 資料中提取有用的對話內容。過濾掉約 97% 的雜訊（系統提示、工具呼叫、思考區塊等），只保留用戶訊息和助手回覆。

附帶一個網頁介面，可以瀏覽、篩選、展開查看所有 session。

## 快速開始

```bash
python3 digest.py --serve
```

正式入口使用 `python3 digest.py --serve` 啟動，預設為 `http://127.0.0.1:8919`。啟動會自動開啟帶前端版本的網址，HTML 不使用瀏覽器快取。

網頁目前提供 session 瀏覽、篩選與專案設定；勾選、匯出與資料來源設定入口暫不顯示。來源沿用既有設定，新安裝使用預設位置；如需修改來源路徑或停用其中一個來源，可編輯 `config.json`（見下方）。

點「設定專案」開啟獨立彈窗。未建立專案時清單為空，點「新增專案」後只需輸入專案名稱與路徑；下方「查看已匯入的專案路徑」預設收合，展開可複製路徑貼入欄位。清單上方可搜尋路徑（不分大小寫，例如 CoinKarma）。列表依每個路徑的 Session 數由多到少排序，計算完整已匯入索引，不受主頁篩選影響。同一專案可填多個新舊路徑，每行一個。儲存後保留設定，取消或關閉不儲存草稿。刪除設定只解除歸屬，不刪除原始 session 或歷史副本。未對應的 session 保留原路徑與舊分類規則。

若要把個人資料與程式分開，啟動時指定位置（每次使用相同參數）：

```bash
python3 digest.py --serve --data-dir "$HOME/.local/share/session-lens"
```

也可設定 `SESSION_LENS_DATA_DIR` 環境變數，MCP server 使用相同變數。新位置會進入首次設定，不會自動搬移舊資料。未指定時相容原本的專案目錄。網頁顯示目前資料位置。

啟動網頁不會先強制掃描，既有設定的背景掃描仍依間隔執行。首次設定後請按「重新掃描」；下次啟動才會啟用背景掃描。

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
  "port": 8919,
  "poll_interval_seconds": 10
}
```

| 欄位 | 說明 |
|------|------|
| `claude_dir` | Claude Code 的資料目錄，預設 `~/.claude` |
| `codex_dir` | Codex 的資料目錄，預設 `~/.codex`。設成 `null` 可關閉 Codex session 掃描 |
| `projects` | 專案列表，每個專案包含 `id`、`name`、`category`、`paths`；建議在網頁編輯。路徑含子目錄，較具體者優先 |
| `categories` | 分類規則。key 是分類名稱，value 是專案路徑中要比對的關鍵字列表 |
| `default_category` | 不符合任何規則時的預設分類 |
| `port` | 網頁介面的 HTTP server port |
| `poll_interval_seconds` | 啟動網頁 server 後的背景增量掃描間隔，預設 10 秒；設成 `0` 可關閉 |

明確專案路徑對應優先；未對應時，session 的專案路徑包含某個分類關鍵字就歸到該分類，第一個符合的舊規則生效。修改專案設定會立即更新既有索引歸屬。Claude 解析優先讀取實際工作目錄；舊索引在下次掃描時重新解析以補齊路徑，來源已消失者仍保留原資料。

## 指令

```bash
python3 digest.py              # 處理 session（增量，只處理新的或有變動的）
python3 digest.py --serve      # 啟動網頁介面，既有設定每 10 秒背景增量掃描
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

## 驗證

```bash
python3 -m unittest discover -s tests -v
```

核心不需要外部依賴；選用 MCP server 另外需要 `mcp` Python 套件。
