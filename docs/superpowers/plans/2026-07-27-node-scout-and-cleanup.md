# node-scout 建置與 session-lens 瘦身 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清掉死排程、新建素材發現專案 node-scout（摘要卡 → 三方位提取 → 素材卡庫）、把 session-lens 瘦身回純 session 工具。

**Architecture:** node-scout 是加工層新專案，讀數據層產出（session-lens 的 `sessions/*.json` 與 second-brain 的 `raw/telegram/*.md`），用 `claude -p` 兩段式加工：先為每個 session 產一張摘要卡（stdout 直收），再把摘要卡＋Telegram 對話塞進 staging prompt 讓 claude 直接寫素材卡檔案（沿用 second-brain 已驗證的 staging file 模式）。session-lens 只搬走 dream 遺留物、拆掉 `mcp_server.py` 的 dream 段，不加任何東西。

**Tech Stack:** Python 3 純標準庫（unittest 測試）、claude CLI（headless `-p`）、cron。

**設計文件:** `/Users/waynechen/Projects/session-lens/docs/superpowers/specs/2026-07-27-project-architecture-design.md`

## Global Constraints

- node-scout 不引入任何第三方依賴（同 session-lens 的零依賴精神），測試用 stdlib `unittest`
- 所有 LLM 呼叫只存在 node-scout（數據層零 LLM）
- session-lens 只搬走與刪除 dream 相關內容，其他一行都不動（手術式修改）
- 所有產出文字（摘要卡、素材卡、提示詞）用繁體中文
- 路徑一律絕對路徑：node-scout 在 `/Users/waynechen/Projects/node-scout/`
- 提取時排除競爭性資訊與他人隱私（人名、金額、公司內部事務）——寫死在 `prompts/extract.md`

---

### Task 1: 清 note_export 死 cron

**Files:**
- Modify: 使用者 crontab（非檔案，用 `crontab` 指令操作）
- Create: `/Users/waynechen/crontab.backup.2026-07-27.txt`（備份）

**Interfaces:**
- Produces: crontab 中不再有 note_export pipeline 那條排程

背景：cron 裡有一條每小時跑 `/Users/waynechen/Desktop/note_export/pipeline.py` 的排程，但該目錄已不存在，每小時失敗一次。只刪這一條和它正上方的註解。**注意：llm-wiki 的兩條排程（`sync_raw.py` 和 `daily_ingest.sh`）保留不動**，llm-wiki 退役是之後的獨立決策。

- [ ] **Step 1: 備份現有 crontab**

```bash
crontab -l > /Users/waynechen/crontab.backup.2026-07-27.txt
wc -l /Users/waynechen/crontab.backup.2026-07-27.txt
```

Expected: 備份檔產生，行數 > 60。

- [ ] **Step 2: 移除目標兩行（註解＋排程）**

要刪的兩行原文：

```
# 每小時同步 Apple Notes + Telegram 到 note_export
0 * * * * cd /Users/waynechen/Desktop/note_export && /opt/anaconda3/bin/python3 pipeline.py >> /Users/waynechen/Desktop/note_export/logs/pipeline.log 2>&1
```

注意不能用 `grep -v note_export` 一把抓——llm-wiki 的註解「同步 note_export 資料到 llm-wiki/raw」也含這個詞，會被誤殺。用精確比對：

```bash
crontab -l | grep -v '^# 每小時同步 Apple Notes + Telegram 到 note_export$' | grep -v '^0 \* \* \* \* cd /Users/waynechen/Desktop/note_export ' | crontab -
```

- [ ] **Step 3: 驗證**

```bash
crontab -l | grep -n 'Desktop/note_export'
crontab -l | grep -c 'llm-wiki'
```

Expected: 第一個指令無輸出（exit 1）；第二個輸出 `4` 左右（llm-wiki 的註解與排程都還在，具體數字以備份檔為準——重點是不為 0）。

---

### Task 2: node-scout 腳手架（目錄、config、提示詞）

**Files:**
- Create: `/Users/waynechen/Projects/node-scout/config.json`
- Create: `/Users/waynechen/Projects/node-scout/.gitignore`
- Create: `/Users/waynechen/Projects/node-scout/prompts/summarize.md`
- Create: `/Users/waynechen/Projects/node-scout/prompts/extract.md`
- Create: `/Users/waynechen/Projects/node-scout/README.md`

**Interfaces:**
- Produces: `config.json` 的欄位 `session_lens_dir`、`telegram_raw_dir`、`days`（Task 3、4、5 的 `load_config()` 讀這些 key）
- Produces: `prompts/summarize.md`（Task 4 直接把它接在 session 內容前面餵給 claude）
- Produces: `prompts/extract.md`（Task 5 把它放進 staging prompt 開頭）

- [ ] **Step 1: 建目錄與 git repo**

```bash
mkdir -p /Users/waynechen/Projects/node-scout/prompts \
         /Users/waynechen/Projects/node-scout/summaries \
         /Users/waynechen/Projects/node-scout/materials
cd /Users/waynechen/Projects/node-scout && git init
```

- [ ] **Step 2: 寫 config.json**

```json
{
  "session_lens_dir": "/Users/waynechen/Projects/session-lens",
  "telegram_raw_dir": "/Users/waynechen/Projects/second-brain/raw/telegram",
  "days": 7
}
```

- [ ] **Step 3: 寫 .gitignore**

```
state.json
.staging_prompt.md
__pycache__/
.DS_Store
```

（`summaries/` 和 `materials/` 是要進版控的——它們是資產，不是快取。）

- [ ] **Step 4: 寫 prompts/summarize.md**

````markdown
你會收到一個 Claude Code / Codex session 的過濾後對話（只含用戶訊息與助手回覆）。
請產出一張「session 摘要卡」。直接輸出 Markdown 內容本身，不要加開場白、結尾或程式碼圍欄。

# <一句話標題：這個 session 在幹嘛>

## 在幹嘛
2-4 句：這個 session 的任務脈絡與目標。

## 解決了什麼
列點：實際完成或決定的事。沒有就寫「無」。

## 學到什麼
列點：踩的坑、想通的道理、做出的判斷與理由。沒有就寫「無」。

## 可分享訊號
列點：可能值得對外分享的線索——新穎做法、特殊框架、反共識判斷、展示執行力的成果。
沒有明顯訊號就寫「無」。這裡只標線索，不做最終判斷。

規則：
- 繁體中文
- 忠於對話內容，不腦補
- 全卡 400 字以內
````

- [ ] **Step 5: 寫 prompts/extract.md**

````markdown
# 素材提取任務

你是「節點價值偵察員」。下方「輸入材料」是我最近的活動紀錄（session 摘要卡與 Telegram 對話）。
任務：從中找出值得對外分享的素材，每個素材寫成一張素材卡，存到 materials/ 目錄。

## 目的（判斷時時刻記住）

我在經營自己在人脈網路中的節點價值。輸出的功能是讓「有認知但缺執行力的人」主動來找我。
所以素材要嘛證明「這個人有料」，要嘛證明「這個人能做」。

## 三個提取方位

1. **有用**：對別人可複製的做法、可遷移的框架、省時間或錢的工具鏈（非競爭性認知，分享不自損）
2. **厲害**：我覺得理所當然但一般人做不到的速度或規模；花大量時間踩坑換到的知識；反共識且有實證的判斷
3. **成熟**：同一主題在多個來源獨立出現（sources 列出所有出現處）

## 不要提取

- 競爭性資訊：具體交易機會、未公開的案子
- 他人隱私：對話對象的人名細節、金額、公司內部事務
- 寒暄、日常瑣事、沒有認知含量的進度回報

## 素材卡格式

每個素材一個檔案：`materials/YYYY-MM-DD-<英文短slug>.md`（日期用下方給的「今天日期」）

```
---
title: <素材一句話>
date: <今天日期>
direction: 有用 | 厲害 | 成熟
sources:
  - <session id 或 telegram 檔名>
audience: <對哪個圈子最有價值，例：中文 AI 圈、傳產、幣圈交易者>
format: 推文 | 文章 | demo
---

## 素材內容

<3-8 句：這個素材是什麼、為什麼值得分享>

## 建議切角

<1-3 個具體的寫法角度>
```

## 規則

- 動手前先讀 materials/ 現有的卡；同一素材已有卡就不要重複建，改在既有卡的 sources 補上新來源
- 寧缺勿濫：一批輸入抓 0-5 張卡是正常的，不要硬湊
- 全部用繁體中文
````

- [ ] **Step 6: 寫 README.md**

````markdown
# node-scout

素材發現 agent：從 Claude Code / Codex session 與 Telegram 對話中，
發現值得對外分享的素材，累積成素材卡庫。目的是經營自己在人脈網路中的節點價值。

## 管線

```
session-lens/sessions/*.json ─→ 摘要卡 (summaries/) ─┐
                                                     ├─→ 三方位提取 ─→ 素材卡 (materials/)
second-brain/raw/telegram/*.md ──────────────────────┘
```

## 用法

```bash
python3 pipeline.py              # 摘要 + 提取（最近 config.days 天，增量）
python3 pipeline.py --summarize  # 只產摘要卡
python3 pipeline.py --extract    # 只跑提取
python3 pipeline.py --days 3     # 覆蓋回看天數
python3 pipeline.py --dry-run    # 只列出會處理什麼，不呼叫 claude
```

設定見 `config.json`。提示詞（靈魂）在 `prompts/`。

設計文件：session-lens repo 的 `docs/superpowers/specs/2026-07-27-project-architecture-design.md`
````

- [ ] **Step 7: Commit**

```bash
cd /Users/waynechen/Projects/node-scout
git add config.json .gitignore prompts/ README.md
git commit -m "chore: node-scout 腳手架（config、提示詞、README）"
```

---

### Task 3: pipeline.py 純函數（TDD）

**Files:**
- Create: `/Users/waynechen/Projects/node-scout/pipeline.py`
- Test: `/Users/waynechen/Projects/node-scout/test_pipeline.py`

**Interfaces:**
- Consumes: `config.json`（Task 2）
- Produces: `select_recent_sessions(index: list[dict], cutoff: str) -> list[dict]`（依 `last_active >= cutoff` 過濾，cutoff 格式 `YYYY-MM-DD`）
- Produces: `format_session(turns: list[dict], max_chars: int = 60000) -> str`（把 `{role, text}` 列表排成文字，超限截斷）
- Produces: `select_recent_telegram(tg_dir: str, cutoff: str) -> list[Path]`（依檔名前 10 碼日期過濾，非日期開頭的檔案跳過）
- Produces: `load_config() -> dict`、`load_state() -> dict`、`save_state(state) -> None`（state 結構：`{"summarized": {session_id: last_active}, "extracted": [路徑字串]}`）

- [ ] **Step 1: 寫失敗測試**

`test_pipeline.py`：

```python
import json
import tempfile
import unittest
from pathlib import Path

import pipeline


class TestSelectRecentSessions(unittest.TestCase):
    def test_filters_by_last_active(self):
        index = [
            {"session_id": "a", "last_active": "2026-07-25 10:00"},
            {"session_id": "b", "last_active": "2026-07-10 10:00"},
        ]
        out = pipeline.select_recent_sessions(index, "2026-07-20")
        self.assertEqual([s["session_id"] for s in out], ["a"])

    def test_missing_last_active_excluded(self):
        out = pipeline.select_recent_sessions([{"session_id": "x"}], "2026-07-20")
        self.assertEqual(out, [])


class TestFormatSession(unittest.TestCase):
    def test_formats_roles(self):
        turns = [{"role": "user", "text": "哈囉"}, {"role": "assistant", "text": "你好"}]
        out = pipeline.format_session(turns)
        self.assertIn("[user] 哈囉", out)
        self.assertIn("[assistant] 你好", out)

    def test_truncates_over_limit(self):
        turns = [{"role": "user", "text": "x" * 100}, {"role": "user", "text": "y" * 100}]
        out = pipeline.format_session(turns, max_chars=120)
        self.assertIn("截斷", out)
        self.assertNotIn("y", out)


class TestSelectRecentTelegram(unittest.TestCase):
    def test_filters_by_filename_date_and_skips_non_dated(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "2026-07-25_Gary.md").write_text("hi")
            Path(d, "2026-07-01_Gary.md").write_text("hi")
            Path(d, "notes.md").write_text("hi")
            out = pipeline.select_recent_telegram(d, "2026-07-20")
            self.assertEqual([p.name for p in out], ["2026-07-25_Gary.md"])


class TestState(unittest.TestCase):
    def test_load_state_default(self):
        orig = pipeline.STATE_FILE
        pipeline.STATE_FILE = Path(tempfile.mkdtemp()) / "state.json"
        try:
            self.assertEqual(pipeline.load_state(), {"summarized": {}, "extracted": []})
        finally:
            pipeline.STATE_FILE = orig


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd /Users/waynechen/Projects/node-scout && python3 -m unittest test_pipeline -v
```

Expected: FAIL/ERROR（`No module named 'pipeline'`）。

- [ ] **Step 3: 寫最小實作**

`pipeline.py`：

```python
#!/usr/bin/env python3
"""node-scout pipeline: session/對話 → 摘要卡 → 素材卡

Usage:
    python3 pipeline.py              # 摘要 + 提取（最近 config.days 天，增量）
    python3 pipeline.py --summarize  # 只產摘要卡
    python3 pipeline.py --extract    # 只跑提取
    python3 pipeline.py --days 3     # 覆蓋回看天數
    python3 pipeline.py --dry-run    # 只列出會處理什麼，不呼叫 claude
"""

import argparse
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "config.json"
STATE_FILE = ROOT / "state.json"
SUMMARIES_DIR = ROOT / "summaries"
MATERIALS_DIR = ROOT / "materials"
STAGING_FILE = ROOT / ".staging_prompt.md"

MAX_SESSION_CHARS = 60_000
BATCH_CHAR_LIMIT = 80_000


def load_config() -> dict:
    return json.loads(CONFIG_FILE.read_text())


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"summarized": {}, "extracted": []}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def select_recent_sessions(index: list, cutoff: str) -> list:
    return [s for s in index if s.get("last_active", "") >= cutoff]


def format_session(turns: list, max_chars: int = MAX_SESSION_CHARS) -> str:
    parts = []
    total = 0
    for t in turns:
        line = f"[{t.get('role', '?')}] {t.get('text', '')}"
        if total + len(line) > max_chars:
            parts.append(f"...（超過 {max_chars} 字元上限，其後截斷）")
            break
        parts.append(line)
        total += len(line)
    return "\n\n".join(parts)


def select_recent_telegram(tg_dir: str, cutoff: str) -> list:
    files = []
    for p in sorted(Path(tg_dir).expanduser().glob("*.md")):
        if not p.name[:4].isdigit():
            continue
        if p.name[:10] >= cutoff:
            files.append(p)
    return files
```

- [ ] **Step 4: 跑測試確認通過**

```bash
cd /Users/waynechen/Projects/node-scout && python3 -m unittest test_pipeline -v
```

Expected: 全部 PASS（6 tests OK）。

- [ ] **Step 5: Commit**

```bash
cd /Users/waynechen/Projects/node-scout
git add pipeline.py test_pipeline.py
git commit -m "feat: pipeline 純函數（session/telegram 篩選、對話排版、state）"
```

---

### Task 4: 摘要卡階段（claude -p）

**Files:**
- Modify: `/Users/waynechen/Projects/node-scout/pipeline.py`（追加 `summarize_stage()` 與 `main()`）

**Interfaces:**
- Consumes: Task 3 的全部函數、Task 2 的 `prompts/summarize.md`
- Produces: `summaries/<session_id>.md`——frontmatter 含 `session_id`、`source`、`project`、`category`、`period`，內文是 claude 產的摘要卡
- Produces: `summarize_stage(cfg: dict, state: dict, cutoff: str, dry_run: bool) -> None`
- Produces: CLI 介面 `--summarize / --extract / --days N / --dry-run`（Task 5、6 靠它跑）

摘要用 `--model haiku`（摘要是機械工作，用便宜模型；提取才需要判斷力，留給預設模型）。stdout 直收，pipeline 負責寫檔與 state——摘要卡檔名是確定性的，不需要讓 agent 自己寫檔。

- [ ] **Step 1: 在 pipeline.py 追加 summarize_stage 與 main**

接在 Task 3 程式碼之後：

```python
def summarize_stage(cfg: dict, state: dict, cutoff: str, dry_run: bool = False) -> None:
    sl_dir = Path(cfg["session_lens_dir"]).expanduser()
    index = json.loads((sl_dir / "index.json").read_text())
    recent = select_recent_sessions(index, cutoff)
    todo = [
        s for s in recent
        if state["summarized"].get(s["session_id"]) != s.get("last_active")
    ]
    print(f"摘要卡：範圍內 {len(recent)} 個 session，需（重新）摘要 {len(todo)} 個")
    prompt_tpl = (ROOT / "prompts" / "summarize.md").read_text()

    for s in todo:
        sid = s["session_id"]
        label = f"{sid} {s.get('project', '')}"
        if dry_run:
            print(f"  [dry-run] {label}")
            continue
        session_file = sl_dir / "sessions" / f"{sid}.json"
        if not session_file.exists():
            print(f"  跳過（找不到檔案）{label}")
            continue
        turns = json.loads(session_file.read_text())
        meta = (
            f"session_id: {sid}\n"
            f"source: {s.get('source', '?')}\n"
            f"project: {s.get('project', '?')}\n"
            f"category: {s.get('category', '?')}\n"
            f"period: {s.get('started_at', '?')} → {s.get('last_active', '?')}"
        )
        full_prompt = (
            f"{prompt_tpl}\n\n---\n\n## Session 資訊\n\n{meta}\n\n"
            f"## 對話內容\n\n{format_session(turns)}"
        )
        r = subprocess.run(
            ["claude", "-p", "--model", "haiku"],
            input=full_prompt, capture_output=True, text=True, timeout=300,
        )
        if r.returncode != 0 or not r.stdout.strip():
            print(f"  失敗 {label}: {r.stderr.strip()[:200]}")
            continue
        card = (
            f"---\n{meta}\n---\n\n{r.stdout.strip()}\n"
        )
        (SUMMARIES_DIR / f"{sid}.md").write_text(card)
        state["summarized"][sid] = s.get("last_active")
        save_state(state)
        print(f"  ✓ {label}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--summarize", action="store_true", help="只產摘要卡")
    ap.add_argument("--extract", action="store_true", help="只跑提取")
    ap.add_argument("--days", type=int, help="覆蓋 config 的回看天數")
    ap.add_argument("--dry-run", action="store_true", help="只列出會處理什麼")
    args = ap.parse_args()

    cfg = load_config()
    state = load_state()
    days = args.days or cfg.get("days", 7)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    print(f"回看 {days} 天（cutoff {cutoff}）")

    run_all = not (args.summarize or args.extract)
    if args.summarize or run_all:
        summarize_stage(cfg, state, cutoff, args.dry_run)
    if args.extract or run_all:
        extract_stage(cfg, state, cutoff, args.dry_run)


if __name__ == "__main__":
    main()
```

（`extract_stage` 在 Task 5 才實作。為了讓本 task 能單獨測，先加一個佔位：）

```python
def extract_stage(cfg: dict, state: dict, cutoff: str, dry_run: bool = False) -> None:
    print("提取：尚未實作（Task 5）")
```

- [ ] **Step 2: 既有測試不能壞**

```bash
cd /Users/waynechen/Projects/node-scout && python3 -m unittest test_pipeline -v
```

Expected: 6 tests OK。

- [ ] **Step 3: dry-run 煙霧測試**

```bash
cd /Users/waynechen/Projects/node-scout && python3 pipeline.py --summarize --days 2 --dry-run
```

Expected: 列出最近 2 天的 session 清單（`[dry-run] <uuid> <專案路徑>` 若干行），不呼叫 claude。

- [ ] **Step 4: 真跑一個 session 驗證**

```bash
cd /Users/waynechen/Projects/node-scout && python3 pipeline.py --summarize --days 1
ls summaries/ && head -30 summaries/$(ls summaries/ | head -1)
```

Expected: 至少一張摘要卡產生，frontmatter 完整、內文有「在幹嘛／解決了什麼／學到什麼／可分享訊號」四段、繁體中文。若品質差（腦補、超長），調 `prompts/summarize.md` 重跑（先刪 `state.json` 對應條目或整檔）。

- [ ] **Step 5: Commit**

```bash
cd /Users/waynechen/Projects/node-scout
git add pipeline.py summaries/
git commit -m "feat: 摘要卡階段（claude -p haiku，stdout 直收，增量 state）"
```

---

### Task 5: 提取階段（三方位素材卡）

**Files:**
- Modify: `/Users/waynechen/Projects/node-scout/pipeline.py`（替換 Task 4 的 `extract_stage` 佔位）

**Interfaces:**
- Consumes: Task 2 的 `prompts/extract.md`、Task 3 的 `select_recent_telegram`、Task 4 產出的 `summaries/*.md`
- Produces: `materials/YYYY-MM-DD-<slug>.md` 素材卡（由 claude agent 直接寫檔，格式定義在 `prompts/extract.md`）
- Produces: `state["extracted"]` 記錄已餵過提取的輸入檔路徑

做法沿用 second-brain 驗證過的模式：組一個 staging prompt 檔（提示詞＋輸入材料全文內嵌），然後 `claude -p "讀取 <staging> 並遵照指示" --permission-mode acceptEdits`，在 node-scout 目錄下執行，讓 agent 直接把素材卡寫進 `materials/`。輸入材料內嵌（而非讓 agent 去讀外部路徑）是為了避開 headless 模式下讀取 cwd 外檔案的權限問題。超過 80,000 字元就分批。

- [ ] **Step 1: 替換 extract_stage 佔位為完整實作**

```python
def extract_stage(cfg: dict, state: dict, cutoff: str, dry_run: bool = False) -> None:
    tg_files = select_recent_telegram(cfg["telegram_raw_dir"], cutoff)
    summary_files = [p for p in sorted(SUMMARIES_DIR.glob("*.md"))]
    candidates = summary_files + tg_files
    todo = [p for p in candidates if str(p) not in state["extracted"]]
    print(f"提取：候選 {len(candidates)} 個輸入，新輸入 {len(todo)} 個")
    if not todo:
        return
    if dry_run:
        for p in todo:
            print(f"  [dry-run] {p}")
        return

    prompt_tpl = (ROOT / "prompts" / "extract.md").read_text()
    today = datetime.now().strftime("%Y-%m-%d")

    def run_batch(batch: list) -> None:
        sections = "\n\n".join(
            f"### 來源：{p.name}\n\n{p.read_text()}" for p in batch
        )
        STAGING_FILE.write_text(
            f"{prompt_tpl}\n\n今天日期：{today}\n\n---\n\n# 輸入材料\n\n{sections}\n"
        )
        r = subprocess.run(
            [
                "claude", "-p",
                f"讀取 {STAGING_FILE.name} 並遵照其中所有指示執行。",
                "--permission-mode", "acceptEdits",
            ],
            cwd=str(ROOT), timeout=3600,
        )
        if r.returncode == 0:
            state["extracted"].extend(str(p) for p in batch)
            save_state(state)
            print(f"  ✓ 批次完成（{len(batch)} 個輸入）")
        else:
            print(f"  批次失敗（{len(batch)} 個輸入），state 未更新，可重跑")

    batch, batch_chars = [], 0
    for p in todo:
        size = len(p.read_text())
        if batch and batch_chars + size > BATCH_CHAR_LIMIT:
            run_batch(batch)
            batch, batch_chars = [], 0
        batch.append(p)
        batch_chars += size
    if batch:
        run_batch(batch)
```

- [ ] **Step 2: 既有測試不能壞**

```bash
cd /Users/waynechen/Projects/node-scout && python3 -m unittest test_pipeline -v
```

Expected: 6 tests OK。

- [ ] **Step 3: dry-run 煙霧測試**

```bash
cd /Users/waynechen/Projects/node-scout && python3 pipeline.py --extract --days 2 --dry-run
```

Expected: 列出候選輸入（Task 4 產的摘要卡＋最近 2 天的 Telegram 檔）。

- [ ] **Step 4: 真跑一小批驗證**

```bash
cd /Users/waynechen/Projects/node-scout && python3 pipeline.py --extract --days 1
ls materials/ && cat materials/*.md 2>/dev/null | head -40
```

Expected: `materials/` 出現 0 到數張素材卡（0 張也可能是正常的——寧缺勿濫），有卡的話 frontmatter 欄位完整（title/date/direction/sources/audience/format）。

- [ ] **Step 5: Commit**

```bash
cd /Users/waynechen/Projects/node-scout
git add pipeline.py materials/
git commit -m "feat: 提取階段（staging prompt + acceptEdits，claude 直寫素材卡，80k 分批）"
```

---

### Task 6: MVP 驗收——跑最近 7 天，用戶審素材卡

**Files:**
- 無新檔案；產出 `summaries/`、`materials/` 內容

**Interfaces:**
- Consumes: 完整管線（Task 4 + 5）

- [ ] **Step 1: 全量跑 7 天**

```bash
cd /Users/waynechen/Projects/node-scout && python3 pipeline.py --days 7
```

Expected: 摘要階段逐一印 `✓`，提取階段分批完成。session 量大時要跑一陣子（每 session 一次 haiku 呼叫）。

- [ ] **Step 2: 整理產出給用戶審**

```bash
ls /Users/waynechen/Projects/node-scout/summaries/ | wc -l
ls /Users/waynechen/Projects/node-scout/materials/
```

把素材卡列給用戶看，請用戶判斷：「這真的值得寫」的比例夠不夠高。

- [ ] **Step 3: 用戶閘門（不可跳過）**

- 比例夠高 → 繼續 Step 4
- 不夠 → 跟用戶收集具體不滿（抓錯方向？太瑣碎？漏掉明顯素材？），改 `prompts/extract.md` 或 `prompts/summarize.md`，把 `state.json` 的 `extracted` 清空重跑提取，回 Step 2。rubric 是靈魂，這裡迭代幾輪是預期內

- [ ] **Step 4: Commit 最終產出與 prompt 調整**

```bash
cd /Users/waynechen/Projects/node-scout
git add -A
git commit -m "feat: MVP 7 天全量跑通，rubric 依驗收回饋調整"
```

---

### Task 7: session-lens 瘦身

**Files:**
- Move: `templates/`、`dream-output/`、`dream-log.json`、`docs/dream-landscape-research.md` → `/Users/waynechen/Projects/second-brain/references/`
- Modify: `/Users/waynechen/Projects/session-lens/mcp_server.py`（拆 dream 段）

**Interfaces:**
- Produces: session-lens 目錄只剩 session 相關內容；`mcp_server.py` 只剩 4 個工具（session_list / session_detail / session_search / session_refresh）

注意：這些檔案在 session-lens 的 git 裡全是未追蹤（`git ls-files` 只有 .gitignore、README.md、config.example.json、digest.py、prototype.html），所以搬移不需要 git 操作。second-brain 不是 git repo，直接 mv。

- [ ] **Step 1: 搬 dream 遺留物到 second-brain/references/**

```bash
mkdir -p /Users/waynechen/Projects/second-brain/references
cd /Users/waynechen/Projects/session-lens
mv templates /Users/waynechen/Projects/second-brain/references/dream-templates
mv dream-output /Users/waynechen/Projects/second-brain/references/dream-output
mv dream-log.json /Users/waynechen/Projects/second-brain/references/dream-log.json
mv docs/dream-landscape-research.md /Users/waynechen/Projects/second-brain/references/dream-landscape-research.md
```

- [ ] **Step 2: 拆 mcp_server.py 的 dream 段**

三個修改（行號以現檔為準）：

1. 刪除第 19-20 行的兩個常數：

```python
TEMPLATES_DIR = BASE_DIR / "templates"
DREAM_LOG_FILE = BASE_DIR / "dream-log.json"
```

2. 刪除第 216 行起的整個 Dream 區塊——從 `# ---` 分隔註解＋`# Dream` 開始，到 `session_dream_log` 函數結尾（`return f"Dream 日誌已更新。..."` 那行）為止，即 `if __name__ == "__main__":` 之前的所有 dream 內容。包含：`_load_dream_log`、`_compress_turns`、`session_dream`、`session_dream_log`。

3. 第 11 行 `from datetime import datetime, timedelta` 整行刪除——dream 段拆掉後，全檔不再用到 datetime/timedelta（session_list 等四個工具只用字串比較）。

- [ ] **Step 3: 驗證 mcp_server.py 語法與殘留引用**

```bash
cd /Users/waynechen/Projects/session-lens
python3 -m py_compile mcp_server.py && echo COMPILE_OK
grep -in "dream\|template\|datetime" mcp_server.py
```

Expected: `COMPILE_OK`；grep 無輸出（exit 1）。

- [ ] **Step 4: 驗證 digest.py 照常運作**

```bash
cd /Users/waynechen/Projects/session-lens && python3 digest.py
ls /Users/waynechen/Projects/session-lens
```

Expected: digest 增量跑完不報錯；目錄清單只剩 session 相關（digest.py、mcp_server.py、prototype.html、config*、README.md、index.json、sessions/、docs/、.state.json、.obsidian、__pycache__）。

- [ ] **Step 5: 回報用戶**

session-lens 是用戶的 repo 且 `digest.py`、`prototype.html` 有用戶自己的未提交修改——**不要擅自 commit**。跟用戶回報瘦身完成，問要不要把設計文件/計畫一起 commit。

---

## 已知限制（記在這裡，不擋 MVP）

1. session 被重新摘要後（last_active 變了），它的摘要卡不會重進提取——`state["extracted"]` 以路徑記錄，不看內容變動。之後有需要再改成 路徑+mtime。
2. 提取階段的 agent 失敗重跑時，同批輸入會整批重餵（state 只在成功後更新），可能產生重複素材卡——`prompts/extract.md` 已要求先讀現有卡去重，靠 rubric 擋。
3. Telegram 只吃 `second-brain/raw/telegram/` 現有檔案；收集器本身沒排程，要新資料得手動跑 second-brain 的 collector。收集器抽出獨立專案是之後的事。
