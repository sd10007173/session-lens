#!/usr/bin/env python3
"""
session-lens digest: 從 Claude Code session JSONL 中提取有用的對話內容。

用法:
  python digest.py            # 處理所有 session，產出 index.json + sessions/*.json
  python digest.py --serve    # 處理後啟動 HTTP server 瀏覽前端
  python digest.py --force    # 忽略快取，重新處理所有 session
"""

import argparse
import http.server
import json
import os
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent
CONFIG_FILE = OUTPUT_DIR / "config.json"
STATE_FILE = OUTPUT_DIR / ".state.json"

SYSTEM_REMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print(f"找不到 {CONFIG_FILE}，請從 config.example.json 複製一份")
        sys.exit(1)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_paths(config: dict) -> tuple[Path, Path]:
    claude_dir = Path(os.path.expanduser(config.get("claude_dir", "~/.claude")))
    projects_dir = claude_dir / "projects"
    return claude_dir, projects_dir


def build_category_rules(config: dict) -> list[tuple[str, str]]:
    rules = []
    for category, patterns in config.get("categories", {}).items():
        for pattern in patterns:
            rules.append((pattern, category))
    return rules


def categorize(project_dir_name: str, rules: list[tuple[str, str]], default: str) -> str:
    for pattern, cat in rules:
        if pattern in project_dir_name:
            return cat
    return default


HOME_PREFIX = str(Path.home()).replace("/", "-").lstrip("-")


def decode_project_path(dirname: str) -> str:
    if dirname.startswith("-" + HOME_PREFIX):
        rest = dirname[len("-" + HOME_PREFIX) :]
        if not rest:
            return "~"
        parts = rest.lstrip("-").split("-")
        return "~/" + "/".join(parts)
    return dirname.replace("-", "/")


def strip_system_reminders(text: str) -> str:
    return SYSTEM_REMINDER_RE.sub("", text).strip()


def extract_user_text(message: dict) -> str | None:
    content = message.get("content", "")
    if isinstance(content, str):
        t = strip_system_reminders(content)
        return t or None
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                t = strip_system_reminders(block)
                if t:
                    parts.append(t)
            elif isinstance(block, dict) and block.get("type") == "text":
                t = strip_system_reminders(block.get("text", ""))
                if t:
                    parts.append(t)
        return "\n".join(parts) if parts else None
    return None


def extract_assistant_text(message: dict) -> str | None:
    content = message.get("content", [])
    if not isinstance(content, list):
        return None
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            t = block.get("text", "").strip()
            if t:
                parts.append(t)
    return "\n".join(parts) if parts else None


def parse_timestamp(ts) -> datetime | None:
    if ts is None:
        return None
    try:
        if isinstance(ts, (int, float)):
            if ts > 1e12:
                return datetime.fromtimestamp(ts / 1000)
            return datetime.fromtimestamp(ts)
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def process_session(jsonl_path: Path) -> dict | None:
    turns = []
    first_ts = None
    last_ts = None

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = parse_timestamp(obj.get("timestamp"))
            if ts:
                if first_ts is None or ts < first_ts:
                    first_ts = ts
                if last_ts is None or ts > last_ts:
                    last_ts = ts

            msg_type = obj.get("type", "")
            if msg_type == "user":
                text = extract_user_text(obj.get("message", {}))
                if text:
                    turns.append({"role": "user", "text": text})
            elif msg_type == "assistant":
                text = extract_assistant_text(obj.get("message", {}))
                if text:
                    turns.append({"role": "assistant", "text": text})

    if not turns:
        return None

    if not first_ts:
        mtime = jsonl_path.stat().st_mtime
        first_ts = last_ts = datetime.fromtimestamp(mtime)

    first_user = next((t["text"] for t in turns if t["role"] == "user"), "")
    last_user = next((t["text"] for t in reversed(turns) if t["role"] == "user"), "")

    return {
        "turns": turns,
        "first_message": first_user[:300],
        "last_message": last_user[:300],
        "message_count": len(turns),
        "started_at": first_ts.strftime("%Y-%m-%d %H:%M"),
        "last_active": last_ts.strftime("%Y-%m-%d %H:%M"),
    }


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def collect_session_files(projects_dir: Path) -> list[tuple[str, Path]]:
    results = []
    if not projects_dir.exists():
        return results
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for p in project_dir.iterdir():
            if p.suffix == ".jsonl" and p.is_file():
                results.append((project_dir.name, p))
    return results


def run_digest(force: bool = False):
    config = load_config()
    _, projects_dir = get_paths(config)
    category_rules = build_category_rules(config)
    default_category = config.get("default_category", "其他")

    sessions_out = OUTPUT_DIR / "sessions"
    sessions_out.mkdir(parents=True, exist_ok=True)

    state = {} if force else load_state()

    existing_index = {}
    index_file = OUTPUT_DIR / "index.json"
    if not force and index_file.exists():
        with open(index_file, "r") as f:
            for item in json.load(f):
                existing_index[item["session_id"]] = item

    files = collect_session_files(projects_dir)
    print(f"掃描到 {len(files)} 個 session 檔案")

    index = []
    processed = 0
    skipped = 0
    errors = 0

    for project_dirname, jsonl_path in files:
        session_id = jsonl_path.stem
        file_size = jsonl_path.stat().st_size
        state_key = str(jsonl_path)

        if state_key in state and state[state_key] == file_size:
            if session_id in existing_index and "last_message" in existing_index[session_id]:
                index.append(existing_index[session_id])
                skipped += 1
                continue

        try:
            result = process_session(jsonl_path)
        except Exception as e:
            print(f"  錯誤: {jsonl_path.name} - {e}")
            errors += 1
            state[state_key] = file_size
            continue

        if not result:
            state[state_key] = file_size
            continue

        detail_file = sessions_out / f"{session_id}.json"
        with open(detail_file, "w", encoding="utf-8") as f:
            json.dump(result["turns"], f, ensure_ascii=False, indent=2)

        project_name = decode_project_path(project_dirname)
        entry = {
            "session_id": session_id,
            "project": project_name,
            "category": categorize(project_dirname, category_rules, default_category),
            "started_at": result["started_at"],
            "last_active": result["last_active"],
            "first_message": result["first_message"],
            "last_message": result["last_message"],
            "message_count": result["message_count"],
            "filtered_size_kb": round(detail_file.stat().st_size / 1024),
        }
        index.append(entry)
        state[state_key] = file_size
        processed += 1

    index.sort(key=lambda x: x["started_at"], reverse=True)

    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    save_state(state)

    total_kb = sum(e["filtered_size_kb"] for e in index)
    print(f"完成: {processed} 新處理, {skipped} 略過 (無變化), {errors} 錯誤")
    print(f"索引: {len(index)} 個 session, 過濾後總計 {total_kb} KB")
    return index


def serve(port: int = None):
    if port is None:
        config = load_config()
        port = config.get("port", 8919)
    os.chdir(OUTPUT_DIR)
    handler = http.server.SimpleHTTPRequestHandler
    handler.extensions_map.update({".json": "application/json"})
    server = http.server.HTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/prototype.html"
    print(f"啟動 server: {url}")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n���停止")


def main():
    parser = argparse.ArgumentParser(description="Session Lens - Claude Code session 過濾工具")
    parser.add_argument("--serve", action="store_true", help="處理後啟動 HTTP server")
    parser.add_argument("--force", action="store_true", help="忽略快取，重新處理所有 session")
    parser.add_argument("--port", type=int, default=None, help="HTTP server port")
    args = parser.parse_args()

    run_digest(force=args.force)

    if args.serve:
        serve(port=args.port)


if __name__ == "__main__":
    main()
