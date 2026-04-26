# Session Lens

Claude Code 的 session 瀏覽工具。從 JSONL 原始紀錄中萃取用戶輸入與模型回覆，過濾掉系統提示等雜訊，產出可搜尋、可分類的 session 索引與前端介面。

## 快速開始

```bash
# 處理所有 session 並啟動瀏覽器
python3 digest.py --serve
```

執行後會：
1. 掃描 Claude Code 的 session 目錄，萃取對話內容
2. 產出 `index.json`（索引）和 `sessions/*.json`（各 session 的精簡對話）
3. 開啟瀏覽器前端（預設 `http://127.0.0.1:8919`）

## Session 來源路徑

預設讀取 `~/.claude/projects/` 底下所有 `.jsonl` 檔案，這是 Claude Code 存放 session 紀錄的位置。

如需修改來源路徑，編輯 `digest.py` 開頭的：

```python
CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"
```

## 分類規則

`digest.py` 中的 `CATEGORY_RULES` 定義了專案路徑與分類的對應關係：

```python
CATEGORY_RULES = [
    ("rbitrage", "套利"),
    ("CoinKarma", "CoinKarma"),
    # 加入你自己的規則...
]
```

路徑中包含關鍵字的 session 會自動歸類，不符合任何規則的歸為「其他」。請依自己的專案名稱自行調整。

## 產出目錄

所有產出都在 `digest.py` 所在的目錄下：

| 檔案 | 說明 |
|------|------|
| `index.json` | session 索引（時間、專案、分類、訊息數等） |
| `sessions/` | 各 session 的精簡對話 JSON |
| `.state.json` | 處理快取，避免重複解析未變動的檔案 |

這三者都在 `.gitignore` 中，不會被 commit。

## 指令參數

```
python3 digest.py              # 只處理，不啟動 server
python3 digest.py --serve      # 處理後開啟瀏覽器
python3 digest.py --force      # 忽略快取，重新處理所有 session
python3 digest.py --port 9000  # 指定 server port
```
