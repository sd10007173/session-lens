#!/usr/bin/env python3
"""
Session Lens MCP Server

讓 Claude Code 直接查詢歷史 session 對話。
依賴 digest.py 產出的 index.json 和 sessions/*.json。
"""

import json
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

BASE_DIR = Path(__file__).parent
INDEX_FILE = BASE_DIR / "index.json"
SESSIONS_DIR = BASE_DIR / "sessions"

mcp = FastMCP("session-lens")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_index() -> list[dict]:
    if not INDEX_FILE.exists():
        return []
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_turns(session_id: str) -> list[dict]:
    p = SESSIONS_DIR / f"{session_id}.json"
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def session_list(
    project: str = "",
    category: str = "",
    since: str = "",
    limit: int = 20,
) -> str:
    """列出 session 索引。

    Args:
        project: 篩選專案路徑（模糊比對，例如 "Arbitrage"）
        category: 篩選分類（例如 "套利"）
        since: 只顯示此日期之後的 session（格式 YYYY-MM-DD）
        limit: 回傳筆數上限，預設 20
    """
    index = _load_index()
    if not index:
        return "索引為空。請先執行 session_refresh 或手動跑 python3 digest.py"

    results = index
    if project:
        results = [s for s in results if project.lower() in s.get("project", "").lower()]
    if category:
        results = [s for s in results if category == s.get("category", "")]
    if since:
        results = [s for s in results if s.get("started_at", "") >= since]

    results = results[:limit]

    if not results:
        return "沒有符合條件的 session。"

    lines = []
    for s in results:
        first = s.get("first_message", "")[:80].replace("\n", " ")
        lines.append(
            f"- **{s['session_id']}**\n"
            f"  專案: {s.get('project', '?')} | 分類: {s.get('category', '?')}\n"
            f"  時間: {s.get('started_at', '?')} → {s.get('last_active', '?')}\n"
            f"  訊息數: {s.get('message_count', 0)} | 大小: {s.get('filtered_size_kb', 0)} KB\n"
            f"  首句: {first}"
        )

    header = f"共 {len(results)} 個 session（總索引 {len(index)} 個）\n\n"
    return header + "\n\n".join(lines)


@mcp.tool()
def session_detail(
    session_id: str,
    role: str = "all",
    offset: int = 0,
    limit: int = 30,
) -> str:
    """讀取特定 session 的對話內容（分頁）。

    Args:
        session_id: Session UUID
        role: 篩選角色 — "user"、"assistant"、"all"
        offset: 從第幾條開始（0-based）
        limit: 回傳筆數上限，預設 30
    """
    turns = _load_turns(session_id)
    if not turns:
        return f"找不到 session {session_id}，可能尚未索引。"

    if role != "all":
        turns = [t for t in turns if t.get("role") == role]

    total = len(turns)
    page = turns[offset : offset + limit]

    if not page:
        return f"沒有更多內容。（總共 {total} 條，offset={offset}）"

    lines = []
    for i, t in enumerate(page):
        idx = offset + i
        r = t.get("role", "?")
        text = t.get("text", "")
        imgs = t.get("images", [])
        img_note = f" [圖片: {', '.join(imgs)}]" if imgs else ""
        lines.append(f"[{idx}] **{r}**{img_note}\n{text}")

    header = f"Session {session_id} — 顯示 {offset}~{offset+len(page)-1} / 共 {total} 條 (role={role})\n\n"
    return header + "\n\n---\n\n".join(lines)


@mcp.tool()
def session_search(
    query: str,
    project: str = "",
    category: str = "",
    limit: int = 10,
) -> str:
    """在所有 session 對話中搜尋關鍵字。

    Args:
        query: 搜尋關鍵字
        project: 篩選專案路徑（模糊比對）
        category: 篩選分類
        limit: 回傳 session 數上限，預設 10
    """
    index = _load_index()
    if not index:
        return "索引為空。請先執行 session_refresh。"

    candidates = index
    if project:
        candidates = [s for s in candidates if project.lower() in s.get("project", "").lower()]
    if category:
        candidates = [s for s in candidates if category == s.get("category", "")]

    query_lower = query.lower()
    hits = []

    for s in candidates:
        turns = _load_turns(s["session_id"])
        matches = []
        for i, t in enumerate(turns):
            text = t.get("text", "")
            if query_lower in text.lower():
                pos = text.lower().index(query_lower)
                start = max(0, pos - 60)
                end = min(len(text), pos + len(query) + 60)
                snippet = text[start:end].replace("\n", " ")
                if start > 0:
                    snippet = "..." + snippet
                if end < len(text):
                    snippet = snippet + "..."
                matches.append({"turn": i, "role": t.get("role", "?"), "snippet": snippet})
        if matches:
            hits.append({"session": s, "matches": matches})
            if len(hits) >= limit:
                break

    if not hits:
        return f"沒有找到包含「{query}」的 session。"

    lines = []
    for h in hits:
        s = h["session"]
        lines.append(
            f"### {s['session_id']}\n"
            f"專案: {s.get('project', '?')} | {s.get('started_at', '?')} | {s.get('message_count', 0)} 條訊息"
        )
        for m in h["matches"][:5]:
            lines.append(f"  [{m['turn']}] {m['role']}: {m['snippet']}")
        if len(h["matches"]) > 5:
            lines.append(f"  ...還有 {len(h['matches'])-5} 處命中")

    header = f"搜尋「{query}」— 命中 {len(hits)} 個 session\n\n"
    return header + "\n\n".join(lines)


@mcp.tool()
def session_refresh(force: bool = False) -> str:
    """重新掃描 JSONL 檔案，更新索引。等同手動跑 python3 digest.py。

    Args:
        force: True 則忽略快取全部重新處理
    """
    sys.path.insert(0, str(BASE_DIR))
    from digest import run_digest

    index = run_digest(force=force)
    return f"完成。索引共 {len(index)} 個 session。"



if __name__ == "__main__":
    mcp.run(transport="stdio")
