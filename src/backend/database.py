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

_DB_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "private",
    "runtime",
)
os.makedirs(_DB_DIR, exist_ok=True)
DB_PATH = os.path.join(_DB_DIR, "codeforge.db")

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
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS uploads (
                   id TEXT PRIMARY KEY,
                   filename TEXT NOT NULL,
                   size INTEGER NOT NULL,
                   content TEXT NOT NULL,
                   created_at INTEGER NOT NULL
               )"""
        )
        # --- Phase 3: imported projects + RAG index + settings -----------
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS projects (
                   id TEXT PRIMARY KEY,
                   name TEXT NOT NULL,
                   file_count INTEGER NOT NULL DEFAULT 0,
                   total_bytes INTEGER NOT NULL DEFAULT 0,
                   created_at INTEGER NOT NULL
               )"""
        )
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS project_files (
                   id TEXT PRIMARY KEY,
                   project_id TEXT NOT NULL,
                   path TEXT NOT NULL,
                   size INTEGER NOT NULL DEFAULT 0,
                   content TEXT NOT NULL,
                   line_count INTEGER NOT NULL DEFAULT 0,
                   created_at INTEGER NOT NULL,
                   UNIQUE(project_id, path)
               )"""
        )
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS embeddings (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   project_id TEXT NOT NULL,
                   file_ref TEXT NOT NULL,
                   chunk_index INTEGER NOT NULL,
                   content TEXT NOT NULL,
                   start_line INTEGER NOT NULL DEFAULT 1,
                   end_line INTEGER NOT NULL DEFAULT 1,
                   embedding BLOB,
                   model TEXT NOT NULL DEFAULT 'nomic-embed-text',
                   created_at INTEGER NOT NULL
               )"""
        )
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_pfiles_proj ON project_files(project_id)")
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_embed_proj ON embeddings(project_id)")
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS settings (
                   key TEXT PRIMARY KEY,
                   value TEXT NOT NULL,
                   updated_at INTEGER
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
    """Full chat INCLUDING messages (the list endpoint only wants summaries)."""
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


# --- Uploads ---------------------------------------------------------------
# Code files attached to chat. Persisted so they survive a backend restart
# (the in-memory dict in main.py is only a runtime cache).

def upload_add(file_id: str, filename: str, content: str, size: int) -> dict:
    ts = _now()
    with _lock:
        get_db().execute(
            """INSERT OR REPLACE INTO uploads (id, filename, size, content, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (file_id, filename, size, content, ts),
        )
        get_db().commit()
    return {"id": file_id, "filename": filename, "size": size, "created_at": ts}


def upload_get(file_id: str) -> dict | None:
    with _lock:
        row = get_db().execute(
            "SELECT * FROM uploads WHERE id = ?", (file_id,)
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "filename": row["filename"],
        "size": row["size"],
        "content": row["content"],
        "created_at": row["created_at"],
    }


def upload_list() -> list[dict]:
    with _lock:
        rows = get_db().execute(
            "SELECT * FROM uploads ORDER BY created_at DESC"
        ).fetchall()
    return [
        {
            "id": r["id"],
            "filename": r["filename"],
            "size": r["size"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def upload_delete(file_id: str) -> bool:
    with _lock:
        cur = get_db().execute(
            "DELETE FROM uploads WHERE id = ?", (file_id,)
        )
        get_db().commit()
    return cur.rowcount > 0


def purge_uploads(max_age_days: int = 7) -> list[tuple[str, str]]:
    """Delete upload rows older than the window.

    Returns the (id, filename) pairs removed, so the caller can delete the
    matching on-disk files (on disk they are named ``{id}_{filename}``).
    """
    cutoff = _now() - max_age_days * 86400
    with _lock:
        conn = get_db()
        rows = conn.execute(
            "SELECT id, filename FROM uploads WHERE created_at < ?", (cutoff,)
        ).fetchall()
        conn.execute("DELETE FROM uploads WHERE created_at < ?", (cutoff,))
        conn.commit()
    return [(r["id"], r["filename"]) for r in rows]


# --- Phase 3: projects (folder imports) ------------------------------------

SKIP_DIRS = {
    "node_modules", ".git", "venv", ".venv", "dist", "build", "__pycache__",
    ".next", ".pytest_cache", ".idea", ".vscode", "coverage", "target",
    "tmp", "cache", ".cache",
}
SKIP_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "CODE_OF_CONDUCT.md"}
MAX_PROJECT_FILE_BYTES = 2 * 1024 * 1024  # per-file import cap (same as uploads)
MAX_PROJECT_FILES = 500                  # hard cap per project (perf guard)


def project_create(name: str, files: list[dict]) -> dict:
    """Store a project + its allowed files. files: [{path, size, content}]"""
    pid = uuid.uuid4().hex[:12]
    ts = _now()
    with _lock:
        conn = get_db()
        conn.execute(
            "INSERT INTO projects (id, name, file_count, total_bytes, created_at) VALUES (?,?,?,?,?)",
            (pid, name, len(files), sum(f["size"] for f in files), ts),
        )
        rows = [
            (uuid.uuid4().hex[:12], pid, f["path"], f.get("size", len(f["content"])),
             f["content"], len(f["content"].splitlines()), ts)
            for f in files
        ]
        conn.executemany(
            "INSERT INTO project_files (id, project_id, path, size, content, line_count, created_at) "
            "VALUES (?,?,?,?,?,?,?)", rows)
        conn.commit()
    return project_get(pid) or {"id": pid, "name": name}


def project_get(project_id: str) -> dict | None:
    with _lock:
        row = get_db().execute("SELECT * FROM projects WHERE id=?",
                               (project_id,)).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "file_count": row["file_count"],
        "total_bytes": row["total_bytes"],
        "created_at": row["created_at"],
        "files": project_files_list(project_id),
    }


def project_list() -> list[dict]:
    with _lock:
        rows = get_db().execute(
            "SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    return [{
        "id": r["id"],
        "name": r["name"],
        "file_count": r["file_count"],
        "total_bytes": r["total_bytes"],
        "created_at": r["created_at"],
    } for r in rows]


def project_delete(project_id: str) -> bool:
    with _lock:
        conn = get_db()
        cur = conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        conn.execute("DELETE FROM project_files WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM embeddings WHERE project_id=?", (project_id,))
        conn.commit()
    return cur.rowcount > 0


def project_files_list(project_id: str) -> list[dict]:
    with _lock:
        rows = get_db().execute(
            "SELECT id, path, size, line_count FROM project_files WHERE project_id=? ORDER BY path",
            (project_id,)).fetchall()
    return [{
        "id": r["id"],
        "path": r["path"],
        "size": r["size"],
        "line_count": r["line_count"],
    } for r in rows]


def project_file_get(file_id: str) -> dict | None:
    with _lock:
        row = get_db().execute(
            "SELECT id, project_id, path, size, content, line_count FROM project_files WHERE id=?",
            (file_id,)).fetchone()
    return dict(row) if row else None


def project_file_get_by_path(project_id: str, path: str) -> dict | None:
    with _lock:
        row = get_db().execute(
            "SELECT id, project_id, path, size, content, line_count "
            "FROM project_files WHERE project_id=? AND path=?",
            (project_id, path)).fetchone()
    return dict(row) if row else None


# --- Phase 3: settings (key/value) ------------------------------------------

DEFAULT_SYSTEM_PROMPT = (
    "You are CodeForge AI, a precise senior-level coding assistant. "
    "Always give concrete, run-ready code. When referencing a file, include "
    "its path and line numbers. Be brief; no filler."
)


def setting_get(key: str, default: str | None = None) -> str | None:
    with _lock:
        row = get_db().execute("SELECT value FROM settings WHERE key=?",
                               (key,)).fetchone()
    return row["value"] if row else default


def setting_set(key: str, value: str) -> None:
    with _lock:
        get_db().execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value, _now()))
        get_db().commit()


def settings_all() -> dict:
    """Return all settings, with defaults applied for known keys."""
    known = {"system_prompt": DEFAULT_SYSTEM_PROMPT, "temperature": "0.7"}
    with _lock:
        rows = get_db().execute("SELECT key, value FROM settings").fetchall()
    out = dict(known)
    for r in rows:
        out[r["key"]] = r["value"]
    return out


# --- Phase 3: embeddings (RAG) ----------------------------------------------

def chunks_add(project_id: str, file_ref: str, rows: list[tuple]) -> int:
    """rows: [(chunk_index, content, start_line, end_line, blob)]

    Replaces the previous chunk set for (project_id, file_ref) — call again
    after file edits to refresh its slice of the index.
    """
    ts = _now()
    with _lock:
        conn = get_db()
        conn.execute("DELETE FROM embeddings WHERE project_id=? AND file_ref=?",
                     (project_id, file_ref))
        conn.executemany(
            "INSERT INTO embeddings (project_id, file_ref, chunk_index, content, "
            "start_line, end_line, embedding, model, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            [(project_id, file_ref, ci, content, sl, el, blob,
              "nomic-embed-text", ts) for ci, content, sl, el, blob in rows])
        conn.commit()
    return len(rows)


def chunks_for_project(project_id: str) -> list[dict]:
    with _lock:
        rows = get_db().execute(
            "SELECT id, file_ref, chunk_index, content, start_line, end_line "
            "FROM embeddings WHERE project_id=? ORDER BY file_ref, chunk_index",
            (project_id,)).fetchall()
    return [dict(r) for r in rows]


def embeddings_clear(project_id: str) -> None:
    with _lock:
        get_db().execute("DELETE FROM embeddings WHERE project_id=?",
                         (project_id,))
        get_db().commit()
