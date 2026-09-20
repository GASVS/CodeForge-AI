"""
SQLite persistence for CodeForge AI — conversation store (Week 3).

Local-first by design: a single file next to the backend, zero setup, no
external service. The frontend treats this as a plain JSON API:

  GET    /api/chats              -> [{id, title, model, updated_at, message_count}]
  GET    /api/chats/{id}         -> {id, title, model, created_at, updated_at, messages:[{role, content, timestamp?}]}
  POST   /api/chats              -> create (body: {title?, messages?}) -> chat dict
  PUT    /api/chats/{id}         -> replace messages (body: {title?, messages}) -> chat dict
  DELETE /api/chats/{id}         -> {ok: true}
  GET    /api/chats/{id}/export?format=json|md  -> file download
"""

import json
import os
import re
import sqlite3
import threading
import time
import uuid

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codeforge.db")

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def get_db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS conversations (
                   id TEXT PRIMARY KEY,
                   title TEXT NOT NULL,
                   model TEXT,
                   created_at INTEGER NOT NULL,
                   updated_at INTEGER NOT NULL,
                   messages_json TEXT NOT NULL DEFAULT '[]'
               )"""
        )
        _conn.commit()
    return _conn


def _now() -> int:
    return int(time.time())


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "model": row["model"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "messages": json.loads(row["messages_json"] or "[]"),
    }


def _summarize(row: sqlite3.Row) -> dict:
    messages = json.loads(row["messages_json"] or "[]")
    return {
        "id": row["id"],
        "title": row["title"],
        "model": row["model"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "message_count": len(messages),
    }


# --- CRUD -----------------------------------------------------------------

def list_conversations(limit: int = 100) -> list[dict]:
    with _lock:
        rows = get_db().execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_summarize(r) for r in rows]


def get_conversation(chat_id: str) -> dict | None:
    with _lock:
        row = get_db().execute(
            "SELECT * FROM conversations WHERE id = ?", (chat_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def create_conversation(title: str | None = None,
                        messages: list | None = None,
                        model: str | None = None) -> dict:
    chat_id = uuid.uuid4().hex
    ts = _now()
    messages = messages or []
    # Auto-title from the first user message if none given
    title = title or _auto_title(messages)
    with _lock:
        get_db().execute(
            """INSERT INTO conversations (id, title, model, created_at, updated_at, messages_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (chat_id, title, model, ts, ts, json.dumps(messages)),
        )
        get_db().commit()
    result = get_conversation(chat_id)
    assert result is not None  # just inserted
    return result


def update_conversation(chat_id: str, title: str | None = None,
                        messages: list | None = None) -> dict | None:
    with _lock:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (chat_id,)
        ).fetchone()
        if row is None:
            return None
        new_title = title if title is not None else row["title"]
        new_messages = messages if messages is not None else json.loads(
            row["messages_json"] or "[]")
        model = row["model"]
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ?, messages_json = ? WHERE id = ?",
            (new_title, _now(), json.dumps(new_messages), chat_id),
        )
        conn.commit()
    return get_conversation(chat_id)


def delete_conversation(chat_id: str) -> bool:
    with _lock:
        cur = get_db().execute(
            "DELETE FROM conversations WHERE id = ?", (chat_id,)
        )
        get_db().commit()
    return cur.rowcount > 0


def _auto_title(messages: list) -> str:
    for m in messages:
        if m.get("role") == "user" and m.get("content"):
            text = re.sub(r"\s+", " ", m["content"]).strip()
            return text[:48] + ("…" if len(text) > 48 else "") or "New chat"
    return "New chat"


# --- Export ----------------------------------------------------------------

def export_chat_md(chat_id: str) -> str | None:
    chat = get_conversation(chat_id)
    if chat is None:
        return None
    lines = [f"# {chat['title']}", ""]
    for m in chat["messages"]:
        who = "🧑 **You**" if m.get("role") == "user" else "🤖 **Assistant**"
        lines.append(f"## {who}\n")
        lines.append(m.get("content", ""))
        lines.append("")
    return "\n".join(lines)


def export_chat_json(chat_id: str) -> str | None:
    chat = get_conversation(chat_id)
    if chat is None:
        return None
    return json.dumps(chat, indent=2)
