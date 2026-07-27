# 個人資訊系統專案架構設計

日期：2026-07-27
狀態：已與用戶確認架構，待實作

## 背景與目標

現有的個人資訊管線散落在多個專案，且有重複與死件：

- session-lens 混入了 dream 萃取模板、dream-output 等加工層遺留物，過度肥大
- 拉 Telegram 有兩套：note_export（目錄已刪但 cron 還在，每小時失敗）和 second-brain 的收集器（能跑）
- 知識庫有兩套：llm-wiki（cron 還在跑）和 second-brain 的 brain/（半成品）

目標：把整件事切成乾淨的兩層——

1. **數據層**：只收集、過濾、瀏覽，零 LLM
2. **加工層**：所有 `claude -p` 呼叫都在這層

並新建一個「素材發現 agent」（node-scout）。它的目的不是寫作工具，是**經營自己在人脈網路中的節點價值**：從活動紀錄中發現值得分享的素材，透過輸出引來 inbound（有人帶著問題主動來找你）。成功指標是 inbound，不是文章數。

## 架構總圖

```
數據層（只收集、過濾、瀏覽，零 LLM）
│
├── session-lens                    瘦身後：只剩 session 的收集/過濾/瀏覽
│     產出：sessions/*.json、index.json
│
└── telegram collector              目前住在 second-brain/collectors/
      產出：raw/telegram/           之後抽成獨立專案，MVP 階段不動

加工層（所有 claude -p 都在這層）
│
├── node-scout（新建）              發現 agent：經營節點的素材發現
│     輸入：session-lens 的 sessions/*.json ＋ telegram raw
│     產出：摘要卡、素材卡庫
│
└── second-brain                    長期知識庫（半成品，之後復活）
      輸入：同樣的數據層產出 ＋ node-scout 的摘要卡

清理
├── note_export 的死 cron           刪除
└── llm-wiki 的每日 claude -p cron  退役與否待決，不擋 MVP
```

## 各專案職責

| 專案 | 職責一句話 | 這次動什麼 |
|---|---|---|
| session-lens | 收 session、過濾、給人和程式看 | 只搬走，不加東西。搬出：`templates/`、`dream-output/`、`dream-log.json`、`docs/dream-landscape-research.md`。保留：`digest.py`、`prototype.html`、`mcp_server.py`（給程式看 session 的介面，屬於「看」的範圍） |
| node-scout | 從活動紀錄裡發現值得放出去的素材 | 新建於 `/Users/waynechen/Projects/node-scout/` |
| second-brain | 把所有來源萃取成長期知識庫 | 程式不動。dream 模板搬來放 `references/`（其 README 本就規劃吸收 dream 模板當萃取提示詞基礎） |

## node-scout 設計

### 目錄結構

```
/Users/waynechen/Projects/node-scout/
├── prompts/
│   ├── summarize.md       # 摘要卡 rubric
│   └── extract.md         # 三方位提取 rubric
├── summaries/             # 每 session 一張摘要卡（markdown，增量產生）
├── materials/             # 素材卡庫（累積、可搜尋）
├── pipeline.py            # 讀數據層 → claude -p → 寫卡
├── state.json             # 哪些 session 已摘要、哪些對話已掃過
└── config.json            # 數據層路徑、掃描範圍
```

### 管線

```
sessions/*.json ─┐
                 ├→ 摘要卡（每 session 一張：在幹嘛、解決了什麼、學到什麼）
telegram raw   ──┘        │
                          ▼
                 三方位提取器（claude -p + extract.md）
                          │
                          ▼
                 素材卡 → materials/
```

### 三方位提取 rubric（草稿，會迭代）

1. **有用**（對別人有用、觀念/做法新穎）：可複製的做法、可遷移的框架、幫別人省時間或錢的工具鏈。理論對應：非競爭性認知，分享不自損，建立「這個人有料」。
2. **厲害**（別人會覺得有點厲害）：自己覺得理所當然但一般人做不到的速度或規模；花大量時間踩坑換到的知識；反共識且有實證的判斷。理論對應：執行力訊號，建立「這個人能做」，是引來 inbound 的直接誘餌。
3. **成熟**（雙重出現）：同一主題在多個 session 或對話中獨立出現（附出現次數與時間跨度）。信念穩定了才值得寫成文章；只有匯流多個數據源的 agent 偵測得到。

### 素材卡欄位

素材描述、來源（session id / 對話）、方位（有用/厲害/成熟）、對哪個池子最有價值（受眾對應，支援跨圈搬運）、建議形式（推文/文章/demo）、日期。

## 執行順序與驗收

| # | 步驟 | 驗證方式 |
|---|---|---|
| 1 | 清 note_export 死 cron | `crontab -l` 沒有那條 |
| 2 | 建 node-scout MVP，手動跑最近 7 天的 session ＋ Telegram | 用戶看素材卡，「這真的值得寫」的比例夠高；不夠就調 prompts/ 再跑 |
| 3 | session-lens 瘦身，dream 遺留物搬到 second-brain/references/ | session-lens 目錄只剩 session 相關；`digest.py --serve` 照常能跑 |

第 2 步 node-scout 直接讀 `second-brain/raw/telegram/`，先不搬 collectors——一次只動一件事；之後 collectors 抽成獨立專案時，node-scout 改 config 路徑即可。

## 不在這次範圍（之後再說）

- collectors 從 second-brain 抽成獨立數據層專案
- second-brain 復活（萃取管線、brain/ 知識庫）
- llm-wiki 退役決策
- 迴響追蹤（哪些輸出真的引來 inbound，回饋修正 rubric）
- 承諾/人脈追蹤（second-brain 的 people/ 既有設計）
- 草稿生成（素材卡 → 文章初稿）
- PLAUD 錄音輸入
