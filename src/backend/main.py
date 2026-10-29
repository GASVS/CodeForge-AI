"""
FastAPI backend for Jev Open Source Dashboard.

Week 1 MVP endpoints:
- POST /api/chat — Stream LLM response (Ollama or cloud)
- GET  /api/models — List available models
- GET  /stream/api/chat — SSE streaming for real-time updates
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
import httpx
import os
import time
import io
import math
import zipfile
import sqlite3
import numpy as np
from typing import Optional, AsyncGenerator, List
import json
import uuid
import shutil
import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import database

import logging as logging_module
from collections import deque
from logging.handlers import RotatingFileHandler

logging_module.basicConfig(level=logging_module.INFO)

# --- Runtime log capture (for the in-app Logs tab) ------------------------
# An in-process ring buffer AND a rotating on-disk file. The /api/logs
# endpoint merges this with the captured server logs (api_server.log /
# vite_dev.log) so the UI shows the full runtime story, most-recent last.
LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "private",
    "runtime",
)
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE_PATH = os.path.join(LOG_DIR, "app.log")

LOG_BUFFER: deque = deque(maxlen=1000)


class _InProcessBufferHandler(logging_module.Handler):
    def emit(self, record: logging_module.LogRecord) -> None:
        try:
            line = self.format(record)
            LOG_BUFFER.append(line)
        except Exception:
            pass


for _handler in (_InProcessBufferHandler(),
                 RotatingFileHandler(LOG_FILE_PATH, maxBytes=1_000_000, backupCount=2, encoding="utf-8")):
    _handler.setFormatter(logging_module.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging_module.getLogger().addHandler(_handler)

logger = logging_module.getLogger(__name__)

from contextlib import asynccontextmanager

# Configuration (must be defined before app creation)
OLLAMA_BASE_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Temporary storage for uploaded files
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/jev-uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# CORS origins — localhost dev by default, override for prod with e.g.
# ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]

# Upload policy
MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB per file
MAX_FILES_PER_REQUEST = 10
MAX_PROJECT_BYTES_TOTAL = 25 * 1024 * 1024  # total zip upload cap for project imports
CHUNK_SIZE = 256 * 1024  # read uploads in bounded chunks (reject > limit without buffering all)
ALLOWED_EXTENSIONS = {
    "py", "js", "ts", "jsx", "tsx", "mjs", "cjs",
    "rb", "go", "rs", "java", "kt", "swift", "c", "cpp", "h", "hpp",
    "cs", "php", "sh", "bash", "zsh", "ps1",
    "html", "css", "scss", "vue", "svelte",
    "json", "yml", "yaml", "toml", "xml", "sql", "md", "txt", "csv", "ini", "env",
}


def _allowed_code_filename(filename: str) -> Optional[str]:
    """Return a sanitized basename if the extension is code/text, else None."""
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]  # strip any path
    base = base.replace("\x00", "").strip()
    if not base or base in (".", ".."):
        return None
    ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""
    if ext not in ALLOWED_EXTENSIONS:
        return None
    return base


def _looks_binary(chunk: bytes) -> bool:
    """Cheap text sniff: NUL bytes in the first chunk ⇒ binary."""
    return b"\x00" in chunk


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown event handler"""
    # Startup: purge stale uploads (> 7 days) — DB rows + on-disk files
    try:
        removed_pairs = database.purge_uploads(max_age_days=7)
        cutoff = time.time() - 7 * 86400
        for file_id, filename in removed_pairs:
            p = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        # orphan on-disk files (no DB row) beyond the retention window
        for entry in os.scandir(UPLOAD_DIR):
            try:
                if time.time_ns() // 1_000_000_000 < cutoff and entry.is_file():
                    os.remove(entry.path)
            except OSError:
                pass
        if removed_pairs:
            print(f"🧹 Purged {len(removed_pairs)} stale upload(s)")
    except Exception as e:
        print(f"⚠️ Upload purge failed: {e}")

    # Startup: hydrate the in-memory upload cache from SQLite (survives restart)
    try:
        for row in database.upload_list():
            file_id = row["id"]
            if file_id not in uploaded_files_store:
                disk_path = os.path.join(UPLOAD_DIR, f"{file_id}_{row['filename']}")
                data = {
                    "filename": row["filename"],
                    "path": disk_path,
                    "size": row["size"],
                    "created_at": row["created_at"],
                }
                content = database.upload_get(file_id)
                data["content"] = content["content"] if content else ""
                uploaded_files_store[file_id] = data
        if uploaded_files_store:
            print(f"📎 Restored {len(uploaded_files_store)} attached file(s) from SQLite")
    except Exception as e:
        print(f"⚠️ Upload restore failed: {e}")

    # Startup: check Ollama
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                print("✅ Ollama detected!")
            else:
                print("⚠️ Ollama not responding properly")
    except Exception as e:
        print(f"❌ Ollama not available: {e}")
        print("Install Ollama: https://ollama.ai")
    yield  # App runs here

app = FastAPI(
    title="Jev Open Source Dashboard API",
    description="Local-first AI coding assistant backend",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for frontend (localhost:3000 by default; override via ALLOWED_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    model_name: Optional[str] = "qwen3.5-9b-64k"  # Updated default
    stream: bool = True
    context_files: Optional[List[str]] = None  # List of uploaded file IDs
    project_ids: Optional[List[str]] = None    # Imported projects → RAG context


# In-memory storage for uploaded files (in production, use database)
uploaded_files_store: dict = {}


@app.post("/api/upload")
async def upload_file(files: List[UploadFile] = File(...)):
    """Upload code files for analysis. Returns file IDs that can be referenced in chat.

    Enforces: ≤10 files/request, ≤2 MB/file (413), code/text extension (415),
    text sniff (415), sanitized basename (no path traversal).
    """
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=413,
            detail=f"Maximum {MAX_FILES_PER_REQUEST} files per request",
        )

    uploaded_files = []
    for file in files:
        safe_name = _allowed_code_filename(file.filename or "")
        if safe_name is None:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type: {file.filename!r} (code/text files only)",
            )

        file_id = str(uuid.uuid4())[:8]
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{safe_name}")

        chunks: List[bytes] = []
        total = 0
        first_chunk: Optional[bytes] = None
        try:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                if len(chunk) and first_chunk is None:
                    first_chunk = chunk
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024*1024)} MB limit",
                    )
                chunks.append(chunk)
        except HTTPException:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload {safe_name}: {e}")

        if first_chunk is not None and _looks_binary(first_chunk):
            raise HTTPException(
                status_code=415,
                detail=f"{safe_name} looks binary — only text/code files are supported",
            )

        content = b"".join(chunks)
        text_content = content.decode("utf-8", errors="ignore")
        with open(file_path, "wb") as f:
            f.write(content)

        # Persist to SQLite (source of truth; survives restart) and cache in memory
        database.upload_add(file_id, safe_name, text_content, total)
        uploaded_files_store[file_id] = {
            "filename": safe_name,
            "path": file_path,
            "size": total,
            "content": text_content,
            "created_at": time.time(),
        }

        uploaded_files.append(
            {"id": file_id, "filename": safe_name, "size": total}
        )

    return {"files": uploaded_files}


@app.get("/api/files")
async def list_uploaded_files():
    """List all active uploaded files"""
    return {
        "files": [
            {"id": fid, "filename": data["filename"], "size": data["size"]}
            for fid, data in uploaded_files_store.items()
        ]
    }


@app.get("/api/files/{file_id}")
async def get_file_content(file_id: str):
    """Get content of uploaded file by ID"""
    if file_id not in uploaded_files_store:
        raise HTTPException(status_code=404, detail="File not found")
    data = uploaded_files_store[file_id]
    return {"id": file_id, "filename": data["filename"], "content": data["content"]}


@app.delete("/api/files/{file_id}")
async def delete_file(file_id: str):
    """Delete an uploaded file (on-disk file + in-memory cache + SQLite row)."""
    if file_id not in uploaded_files_store and database.upload_get(file_id) is None:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        if file_id in uploaded_files_store:
            path = uploaded_files_store[file_id].get("path")
            if path and os.path.exists(path):
                os.remove(path)
            del uploaded_files_store[file_id]
        # also remove the persisted row so it doesn't revive on next start
        database.upload_delete(file_id)
        return {"message": "File deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Projects (folder imports) — P3.1
#
# Endpoint contract: import a project by JSON `{name, files: [{path, content}]}`
# or by uploading a zip; the walk skips node_modules/.git/venv/lockfiles, files
# over 2 MB, disallowed extensions, and caps imports at 500 files. Project file
# IDs are usable with /stream/api/chat + /api/chat exactly like upload IDs.
# ---------------------------------------------------------------------------


async def _import_project_files(name: str, raw_files: List[dict]) -> dict:
    """Store a project from an already-validated raw file list, then build its
    RAG index (P3.2) as best effort — the import itself must never fail because
    the embedding model is down."""
    if not raw_files:
        raise HTTPException(status_code=422, detail="No files provided")
    normalized: list[dict] = []
    seen_paths: set[str] = set()
    for f in raw_files:
        if f.get("size") is None:
            continue  # already rejected during validation
        path = f.get("path")
        if path in seen_paths:
            continue  # duplicate path within the same import — first wins
        seen_paths.add(path)
        normalized.append({
            "path": path,
            "size": f["size"],
            "content": f["content"],
        })
    if not normalized:
        raise HTTPException(status_code=422, detail="No files provided")
    if len(normalized) > database.MAX_PROJECT_FILES:
        raise HTTPException(
            status_code=413,
            detail=f"Too many files: {len(normalized)} "
                   f"(maximum {database.MAX_PROJECT_FILES})",
        )
    # Uniqueness guard for the project name (projects table has no unique index)
    with database._lock:
        taken = database.get_db().execute(
            "SELECT 1 FROM projects WHERE name=?", (name,)).fetchone()
    if taken:
        raise HTTPException(status_code=409, detail=f"A project named '{name}' already exists")
    try:
        proj = database.project_create(name, normalized)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"A project named '{name}' already exists")
    # P3.2: embed the project's files now so the semantic-search endpoints work
    # immediately after import. Failure (embedding model down, Ollama 5xx) just
    # logs — `POST /{id}/index` can rebuild the index later.
    try:
        stats = await project_index(proj["id"])
        logger.info("Project %s indexed: %s chunks across %s files",
                    proj["id"], stats.get("chunks", 0), stats.get("files_indexed", 0))
    except HTTPException as e:
        logger.warning("Project %s imported but not indexed: %s", proj.get("name"), e.detail)
    return proj


def _validate_json_files(payload: dict) -> list[dict]:
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Missing required field: name")
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise HTTPException(status_code=422, detail="Missing required field: files[]")
    if len(files) > database.MAX_PROJECT_FILES:
        raise HTTPException(
            status_code=413,
            detail=f"Too many files: {len(files)} "
                   f"(maximum {database.MAX_PROJECT_FILES})",
        )
    out: list[dict] = []
    for f in files:
        if not isinstance(f, dict) or not isinstance(f.get("path"), str):
            raise HTTPException(
                status_code=422, detail=f"Each file needs a 'path': {f!r}")
        path = f["path"].replace("\\", "/").strip()
        if not path or path.startswith("/") or ".." in path.split("/"):
            raise HTTPException(
                status_code=422, detail=f"Bad file path (must be relative): {f['path']!r}")
        base = path.rsplit("/", 1)[-1]
        ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=415, detail=f"Unsupported file type: {base!r}")
        content = f.get("content")
        if not isinstance(content, str):
            raise HTTPException(status_code=422, detail=f"File '{path}' needs string 'content'")
        out.append({
            "path": path,
            "size": len(content.encode("utf-8")),
            "content": content,
        })
    return [{"name": name, "files": out}]


async def _zip_to_files(file: UploadFile) -> tuple[str, list[dict]]:
    """Extract an upload zip into importable file entries (with all cap checks).

    Read with the same chunked pattern as /api/upload — real uploads are
    async-only files, so ``file.file.read()`` (sync) would raise RuntimeError.
    """
    if file.size is not None and file.size > MAX_PROJECT_BYTES_TOTAL:
        raise HTTPException(status_code=413, detail="Zip too large")
    chunks: List[bytes] = []
    total = 0
    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_PROJECT_BYTES_TOTAL:
            raise HTTPException(status_code=413, detail="Zip too large")
        chunks.append(chunk)
    try:
        zf = zipfile.ZipFile(io.BytesIO(b"".join(chunks)), "r")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=415, detail="Not a valid zip file")
    name = (file.filename or "project").rsplit(".", 1)[0].strip() or "project"
    files: list[dict] = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        parts = info.filename.replace("\\", "/").split("/")
        if any(p in database.SKIP_DIRS for p in parts[:-1]):
            continue
        base = parts[-1]
        if base in database.SKIP_FILES or base.startswith("."):
            continue
        ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""
        if ext not in ALLOWED_EXTENSIONS:
            continue
        if info.file_size > database.MAX_PROJECT_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"'{info.filename}' exceeds {database.MAX_PROJECT_FILE_BYTES // (1024 * 1024)} MB per-file limit",
            )
        try:
            text = zf.read(info).decode("utf-8", errors="replace")
        except Exception:
            continue  # symlink stubs in zips read as garbage — drop them
        if "\x00" in text:
            continue
        raw_len = len(text.encode("utf-8"))
        if raw_len > database.MAX_PROJECT_FILE_BYTES:
            # Truncating can cut a line mid-way — if so, stop at the last
            # complete line so no half-line is stored.
            text = text[:database.MAX_PROJECT_FILE_BYTES]
            line_end = text.rfind("\n", len(text) - 4096)
            if line_end > 0:
                text = text[:line_end]
        files.append({"path": info.filename, "size": len(text.encode("utf-8")),
                      "content": text})
    if not files:
        raise HTTPException(status_code=422, detail="No importable files in the zip")
    if len(files) > database.MAX_PROJECT_FILES:
        raise HTTPException(
            status_code=413,
            detail=f"Too many files: {len(files)} "
                   f"(maximum {database.MAX_PROJECT_FILES})",
        )
    return name, files


@app.post("/api/projects")
async def create_project(request: Request):
    """Import a project (folder) — JSON body `{name, files:[{path, content}]}` or a zip.

    Dispatch on content type (like /api/upload): a `File(...)`-typed param would
    force FastAPI to parse EVERY body as multipart and the JSON path would 422.
    """
    ctype = request.headers.get("content-type", "").lower()
    if "multipart/form-data" in ctype:
        form = await request.form()
        zip_item = form.get("zip")
        # Starlette form values that aren't files are plain `str`; the zip
        # arrives as a starlette UploadFile (NOT a fastapi one), so check the
        # type idiomatically (is-not-str) rather than via isinstance(fastapi).
        if zip_item is None or isinstance(zip_item, str):
            raise HTTPException(
                status_code=422,
                detail="Zip upload must use the multipart file field 'zip'",
            )
        name, files = await _zip_to_files(UploadFile(file=zip_item.file,
                                                     filename=zip_item.filename,
                                                     headers=zip_item.headers))
        return await _import_project_files(name, files)
    if "application/json" in ctype:
        payload = await request.json()
        parsed = _validate_json_files(payload)
        return await _import_project_files(parsed[0]["name"], parsed[0]["files"])
    raise HTTPException(
        status_code=422,
        detail="Import a project: send JSON {name, files:[{path, content}]} or a zip upload",
    )


@app.get("/api/projects")
async def list_projects():
    """List imported projects (no file contents)."""
    return {"projects": database.project_list()}


@app.get("/api/projects/{project_id}")
async def get_project_endpoint(project_id: str):
    proj = database.project_get(project_id)
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@app.delete("/api/projects/{project_id}")
async def delete_project_endpoint(project_id: str):
    if not database.project_delete(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}


@app.get("/api/projects/{project_id}/files/{file_id}")
async def get_project_file_endpoint(project_id: str, file_id: str):
    f = database.project_file_get(file_id)
    if f is None or f.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="File not found in project")
    return f


@app.get("/")
async def root():
    return {"message": "Jev Open Source Dashboard API", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


# Log files written by start.sh (uvicorn + vite dev output), most-recent last.
_RUNTIME_LOG_FILES = ("api_server.log", "vite_dev.log")
_TAIL_BYTES = 64 * 1024  # only read the tail of each file (bounded read)


def _read_tail(log_dir: str, name: str) -> List[str]:
    path = os.path.join(log_dir, name)
    if not os.path.isfile(path):
        return []
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size > _TAIL_BYTES:
                f.seek(size - _TAIL_BYTES)
            raw = f.read()
        text = raw.decode("utf-8", errors="replace")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        return lines[-200:]
    except OSError:
        return []


@app.get("/api/logs")
async def api_logs():
    """Recent runtime logs (in-process ring buffer + server/dev tails)."""
    server_lines: List[str] = []
    for name in _RUNTIME_LOG_FILES:
        server_lines.extend(_read_tail(LOG_DIR, name))
    lines = server_lines + list(LOG_BUFFER)
    if not lines:
        lines = [f"[{time.strftime('%H:%M:%S')}] (no log entries yet)"]
    return {"lines": lines, "count": len(lines)}



def add_file_context(message: str, context_files: List[str]) -> str:
    """Add uploaded file contents to the prompt for code-aware chat.

    Accepts both uploaded-file IDs and project file IDs (P3.1 folder imports);
    project files are labelled with their in-repo path so the model can cite it.
    """
    if not context_files:
        return message
    
    file_contents = []
    for file_id in context_files[:5]:  # Limit to 5 files to stay within context window
        if file_id in uploaded_files_store:
            data = uploaded_files_store[file_id]
            content = data["content"]
            filename = data["filename"]
            file_contents.append(f"File: {filename}\n```\n{content}\n```")
            continue
        # Project file (from a folder import)
        pf = database.project_file_get(file_id)
        if pf is not None:
            content = pf["content"]
            label = pf["path"]
            proj = database.project_get(pf["project_id"])
            if proj is not None:
                label = f"{proj['name']}/{pf['path']}"
            file_contents.append(f"File: {label}\n```\n{content}\n```")
    
    if not file_contents:
        return message
    
    context_header = f"\n\nI have the following files for context:\n\n" + "\n\n".join(file_contents)
    return message + context_header


# ---------------------------------------------------------------------------
# P3.2 — Semantic search (RAG)
#
# On import, each project file is split into overlapping chunks that are
# embedded with Ollama's local embedding model and stored in the `embeddings`
# table. `project_search` cosine-ranks the chunks against a query, and
# `_rag_context` turns the top-k picks into a labelled block prepended to the
# model prompt for chat. numpy does the vector math — no ChromaDB needed.
# ---------------------------------------------------------------------------
EMBED_MODEL = "nomic-embed-text"
EMBED_BATCH = 16          # chunks per Ollama /api/embed call (bounds memory)
CHUNK_TOKENS = 200        # ~200-token target per chunk (≈1/4 token per char)
CHUNK_OVERLAP = 20        # tokens of overlap between consecutive chunks
EMBED_CHARS = 2048        # ~1024 tokens — a safe single-chunk ceiling
EMBED_CHARS_HARD = 10000  # split anything bigger so no single call is huge
MAX_SEARCH_CHARS = 4000   # per-chunk ceiling in the injected context block
RAG_CONTEXT_CHUNKS = 8    # how many picks to feed into the model prompt


def _split_chunks(text: str) -> list[tuple[int, str]]:
    """Split text into (start_line, chunk_text) pairs.

    ~CHUNK_TOKENS (~800 chars) per chunk with a line-boundary overlap so no
    content is dropped at the seam. Small files come back as one chunk.
    start_line is the file 1-based line where the chunk begins.
    """
    lines = text.split("\n")
    target = min(EMBED_CHARS, max(CHUNK_TOKENS * 4, 64))
    overlap = max(6, min(CHUNK_OVERLAP * 4, target // 3))

    out: list[tuple[int, str]] = []
    window: list[str] = []      # lines in the current chunk (not yet flushed)
    window_start = 1            # file line no of window[0]
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        # Would adding this line overflow the target? Flush first if nonempty.
        cur_len = sum(len(l) + 1 for l in window)
        if window and cur_len + len(line) > target:
            out.append((window_start, "\n".join(window)))
            # Keep the tail as overlap for the next window (line-granularity).
            overlap_lines: list[str] = []
            overlap_len = 0
            for prev in reversed(window):
                if overlap_len + len(prev) + 1 > overlap and overlap_lines:
                    break
                overlap_lines.insert(0, prev)
                overlap_len += len(prev) + 1
            window = overlap_lines
            window_start = (i - len(window)) + 1
            cur_len = sum(len(l) + 1 for l in window)
        if not window:
            window_start = i + 1
        window.append(line)
        i += 1
    if window:
        out.append((window_start, "\n".join(window)))

    # A single line longer than the hard cap still has to fit a request.
    expanded: list[tuple[int, str]] = []
    for sl, c in out:
        if len(c) <= EMBED_CHARS_HARD:
            expanded.append((sl, c))
            continue
        for j in range(0, len(c), EMBED_CHARS_HARD):
            expanded.append((sl, c[j:j + EMBED_CHARS_HARD]))
    return [(sl, c) for sl, c in expanded if c.strip()]


async def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts via Ollama (batched). Order-preserving result."""
    out: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH):
        batch = texts[start:start + EMBED_BATCH]
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/embed",
                json={"model": EMBED_MODEL, "input": batch},
            )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Embedding model '{EMBED_MODEL}' unavailable "
                       f"(Ollama HTTP {resp.status_code})",
            )
        data = resp.json()
        embs = data.get("embeddings") or []
        if len(embs) != len(batch):
            raise HTTPException(
                status_code=502,
                detail=f"Ollama returned {len(embs)} embeddings for {len(batch)} inputs",
            )
        out.extend(embs)
    return out


async def project_index(project_id: str) -> dict:
    """Embed every file in a project into the RAG index (idempotent)."""
    files = database.project_files_with_content(project_id)
    total_chunks = 0
    for f in files:
        chunks = _split_chunks(f["content"])
        total_chunks += len(chunks)
        if not chunks:
            continue
        texts = [c for _sl, c in chunks]
        embs = await _embed_texts(texts)
        rows = [
            (idx, content,
             sl, sl + max(0, content.count("\n")),
             np.asarray(emb, dtype=np.float32).tobytes())
            for idx, (sl, content), emb in zip(range(len(chunks)), chunks, embs)
        ]
        database.chunks_add(project_id, f["id"], rows)
    return {
        "ok": True,
        "project_id": project_id,
        "files_indexed": len(files),
        "chunks": total_chunks,
    }


def _cosine(query: np.ndarray, vecs: np.ndarray) -> np.ndarray:
    """Cosine similarity of one query vector against a matrix of vectors."""
    qn = np.linalg.norm(query)
    if qn == 0:
        return np.zeros(len(vecs))
    qn2 = query / qn
    nn = np.linalg.norm(vecs, axis=1, keepdims=True)
    nn[nn == 0] = 1.0
    return (vecs / nn) @ qn2


async def project_search(project_id: str, query: str, k: int = 10) -> dict:
    """Cosine top-k chunks for a project against a natural-language query."""
    k = max(1, min(k, 50))
    chunks = database.chunks_with_paths(project_id)
    if not chunks:
        return {"query": query, "k": k, "results": []}
    vecs = np.stack([np.frombuffer(c["embedding"], dtype=np.float32) for c in chunks])
    qv = np.asarray((await _embed_texts([query]))[0], dtype=np.float32)
    sim = _cosine(qv, vecs)
    order = sim.argsort()[::-1][:k]
    results = []
    for idx in order:
        c = chunks[idx]
        snippet = c["content"]
        results.append({
            "file": c["file_path"],
            "chunk_index": c["chunk_index"],
            "start_line": c["start_line"],
            "end_line": c["end_line"],
            "score": round(float(sim[idx]), 4),
            "content": snippet,       # full chunk text (for context building)
            "snippet": snippet[:MAX_SEARCH_CHARS],  # truncated (for the search UI)
        })
    return {"query": query, "k": k, "results": results}


def _fmt_snippet(c: dict) -> str:
    head = f"{c['start_line']}-{c['end_line']}" if c.get("start_line") else "?"
    return (
        f"### {c.get('file') or 'file'} (lines {head})\n"
        f"```\n{c.get('content') or c.get('snippet') or ''}\n```"
    )


async def _rag_context_for_question(project_ids: list[str], question: str) -> tuple[str, int]:
    """Search each selected project with the user's question and assemble a
    labelled code-context block for the prompt. Returns ('', 0) if nothing."""
    picks: list[dict] = []
    for pid in project_ids:
        try:
            res = await project_search(pid, question, k=RAG_CONTEXT_CHUNKS)
        except HTTPException:
            continue  # project mid-index / embeddings gone — skip, keep the rest
        picks.extend(res.get("results", []))
    if not picks:
        return ("", 0)
    header = (
        "\n\nHere is the most relevant code from the imported project "
        "(file:line references). Use it to ground your answer:\n\n"
        + "\n\n".join(_fmt_snippet(c) for c in picks)
    )
    return (header, len(picks))


@app.post("/api/projects/{project_id}/index")
async def project_index_endpoint(project_id: str):
    """(Re)build the RAG index for a project. Idempotent — safe to re-call."""
    if database.project_get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    database.embeddings_clear(project_id)
    return await project_index(project_id)


@app.get("/api/projects/{project_id}/search")
async def project_search_endpoint(project_id: str, q: str, k: int = 10):
    """Cosine top-k semantic search over the project's indexed chunks."""
    if database.project_get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not q or not q.strip():
        raise HTTPException(status_code=422, detail="'q' (the query) is required")
    return await project_search(project_id, q.strip(), k=k)


# P7.2 patch/diff apply
class ApplyPatchRequest(BaseModel):
    patch: str


def _apply_unified_diff(original: str, diff_text: str) -> str:
    """Apply a unified diff to original text. Returns the patched text.

    Supports single-file unified diffs (the standard `diff --git` /
    `--- a/…` / `+++ b/…` format). Raises ValueError on malformed input.
    """
    lines = original.splitlines(keepends=True)
    out = list(lines)

    # Strip diff headers (--- / +++) and keep only hunk lines
    hunk_lines: list[str] = []
    in_hunk = False
    for raw in diff_text.splitlines():
        if raw.startswith('--- '):
            continue
        if raw.startswith('+++ '):
            continue
        if raw.startswith('diff --git'):
            continue
        if raw.startswith('index '):
            continue
        if raw.startswith('@@'):
            in_hunk = True
        if not in_hunk and not raw.startswith((' ', '+', '-', '@@')):
            continue
        hunk_lines.append(raw)

    # Parse hunks and apply in reverse order (so line numbers stay valid)
    # Hunk header: @@ -old_start,old_count +new_start,new_count @@
    import re
    hunks: list[tuple[int, int, int, int, list[str]]] = []
    current = None
    current_body: list[str] = []

    for line in hunk_lines:
        m = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
        if m:
            if current is not None:
                hunks.append(current)
            current = (
                int(m.group(1)),
                int(m.group(2) or 1),
                int(m.group(3)),
                int(m.group(4) or 1),
                [],
            )
            continue
        if current is not None:
            current_body.append(line)

    if current is not None:
        hunks.append(current)

    for old_start, old_count, new_start, new_count, body in reversed(hunks):
        old_start_0 = max(0, old_start - 1)
        old_end = old_start_0 + old_count

        replacements: list[str] = []
        for b in body:
            if b.startswith(' ') or b.startswith('+') or b.startswith('-'):
                if b.startswith('+'):
                    replacements.append(b[1:] + '\n')
                elif b.startswith('-'):
                    continue
                else:
                    replacements.append(b[1:] + '\n')
            else:
                replacements.append(b + '\n')

        out[old_start_0:old_end] = [r if r.endswith('\n') else r for r in replacements]

    return ''.join(out)


@app.post("/api/projects/{project_id}/apply-patch")
async def apply_patch(project_id: str, body: ApplyPatchRequest):
    """Apply a unified diff patch to a project file.

    Request body: `{"patch": "unified diff text"}`

    The diff must contain `--- a/<path>` and `+++ b/<path>` headers.
    Returns `{ok, file_id, path, size, line_count}` or 422 on failure.
    """
    if database.project_get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    diff_text = body.patch.strip()
    if not diff_text:
        raise HTTPException(status_code=422, detail="patch is empty")

    # Extract target file path from the diff headers
    target_path = None
    for line in diff_text.splitlines():
        if line.startswith('--- a/'):
            target_path = line[len('--- a/'):]
            break
        if line.startswith('--- '):
            target_path = line[len('--- '):]
            if target_path.startswith('a/'):
                target_path = target_path[2:]
            break

    if not target_path:
        raise HTTPException(status_code=422, detail="Could not find target file path in diff (need '--- a/<path>')")

    file_row = database.project_file_get_by_path(project_id, target_path)
    if file_row is None:
        raise HTTPException(status_code=404, detail=f"File '{target_path}' not found in project")

    try:
        patched = _apply_unified_diff(file_row['content'], diff_text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Malformed patch: {e}")

    updated = database.project_file_update(file_row['id'], patched)
    if updated is None:
        raise HTTPException(status_code=500, detail="Failed to write patched file")

    # P7.2: re-index that file in RAG so search reflects the change
    try:
        chunks = _split_chunks(patched)
        texts = [c for _sl, c in chunks]
        embs = await _embed_texts(texts)
        rows = [
            (idx, content, sl, sl + max(0, content.count('\n')), np.asarray(emb, dtype=np.float32).tobytes())
            for idx, (sl, content), emb in zip(range(len(chunks)), chunks, embs)
        ]
        database.chunks_add(project_id, file_row['id'], rows)
    except HTTPException:
        pass  # best-effort: embedding model down doesn't break the apply

    return {"ok": True, **updated, "path": target_path}


def _system_prompt() -> str:
    """System prompt from the SQLite settings store (per P3.4)."""
    return (database.setting_get("system_prompt", database.DEFAULT_SYSTEM_PROMPT) or "").strip()


def _temperature() -> float:
    raw = database.setting_get("temperature", "0.7") or "0.7"
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return 0.7
    if not math.isfinite(v):  # nan/inf would otherwise slip past the clamp
        return 0.7
    return max(0.0, min(1.0, v))


def _ollama_options() -> dict:
    return {"temperature": _temperature(), "num_ctx": 8192}


# ---------------------------------------------------------------------------
# Settings (P3.4) — read/write the persisted assistant settings + Ollama status
# ---------------------------------------------------------------------------
class SettingsUpdate(BaseModel):
    temperature: Optional[float] = None
    system_prompt: Optional[str] = None


@app.get("/api/settings")
async def api_get_settings():
    """Current assistant settings (defaults applied for absent keys)."""
    return {
        "temperature": _temperature(),
        "system_prompt": _system_prompt(),
    }


@app.put("/api/settings")
async def api_update_settings(body: SettingsUpdate):
    """Persist settings. `temperature` clamped to [0,1] (nan/inf -> 0.7);
    `system_prompt` max 4000 chars. Both are optional — send only what changed."""
    updates: dict = {}
    if body.temperature is not None:
        try:
            t = float(body.temperature)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="temperature must be a number")
        if not math.isfinite(t):
            t = 0.7
        t = max(0.0, min(1.0, t))
        database.setting_set("temperature", repr(t))
        updates["temperature"] = t
    if body.system_prompt is not None:
        sp = body.system_prompt.strip()
        if len(sp) > 4000:
            raise HTTPException(status_code=422, detail="system_prompt too long (max 4000 chars)")
        database.setting_set("system_prompt", sp)
        updates["system_prompt"] = sp
    return {"ok": True, "updated": list(updates), **(await api_get_settings())}


@app.get("/api/ollama/status")
async def api_ollama_status():
    """Is Ollama reachable + how many models are installed (live probe)."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
        models = r.json().get("models", [])
        return {
            "up": True,
            "model_count": len(models),
            "models": [m["name"] for m in models],
            "base_url": OLLAMA_BASE_URL,
        }
    except Exception as e:
        return {
            "up": False,
            "model_count": 0,
            "models": [],
            "base_url": OLLAMA_BASE_URL,
            "error": str(e)[:200],
        }


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Main chat endpoint with optional file context"""
    try:
        # Add file context if uploaded files are provided
        enhanced_message = request.message
        model_to_use = request.model_name or "qwen3.5-9b-64k"
        if request.context_files:
            enhanced_message = add_file_context(request.message, request.context_files)

        # P3.2: imported projects → RAG-picked context (top relevant chunks)
        prefix = ""
        if request.project_ids:
            pids = [p.strip() for p in request.project_ids if p and p.strip()]
            if pids:
                prefix, _count = await _rag_context_for_question(pids, request.message)

        if not OPENROUTER_API_KEY:  # Default to local Ollama
            response = await call_ollama(enhanced_message, model_to_use, prefix_context=prefix)
        else:
            response = await call_openrouter(enhanced_message)
        
        return {"type": "text", "content": response}
    
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503, 
            detail="Cannot connect to Ollama. Make sure it's running: `ollama serve`"
        )
    except HTTPException:
        # Clean errors (e.g. 502 model-not-found from call_ollama) pass through as-is
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def call_ollama(prompt: str, model_name: str, prefix_context: str = "") -> str:
    """Call local Ollama API (non-streaming).

    ``prefix_context`` is optional code context (RAG picks for project mode)
    sent ahead of the user message so the model grounds its answer in the repo.
    """
    # prefix_context is prepended as a labelled code-context block (same shape as
    # add_file_context's upload/project blocks) — model-agnostic, no extra Ollama
    # field required. Empty for the classic file-ids flow.
    full_prompt = (
        (prefix_context.rstrip() + "\n\n" + prompt) if prefix_context else prompt
    )
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": _system_prompt()},
                    {"role": "user", "content": full_prompt},
                ],
                "stream": False,
                "options": _ollama_options(),
            }
        )

        if response.status_code in (400, 404):
            raise HTTPException(
                status_code=502,
                detail=f"Model '{model_name}' not available in Ollama",
            )
        if response.status_code >= 500:
            raise HTTPException(status_code=502, detail=f"Ollama error: HTTP {response.status_code}")

        result = response.json()
        if result.get("error"):
            raise HTTPException(status_code=502, detail=f"Ollama error: {result['error']}")
        return result.get("message", {}).get("content", "")


# P7.1 tool registry — populated by later phases (code indexer, etc.)
TOOL_REGISTRY: dict[str, dict] = {}

def register_tool(name: str, description: str, parameters: dict, handler):
    TOOL_REGISTRY[name] = {
        "name": name,
        "description": description,
        "parameters": parameters,
        "handler": handler,
    }

async def _execute_tool_call(tool_call: dict) -> dict:
    name = tool_call.get("function", {}).get("name", "")
    args = tool_call.get("function", {}).get("arguments", {})
    tool = TOOL_REGISTRY.get(name)
    if not tool:
        return {"name": name, "result": {"error": f"Unknown tool: {name}"}}
    try:
        result = tool["handler"](args)
        if asyncio.iscoroutine(result):
            result = await result
        return {"name": name, "result": result}
    except Exception as e:
        return {"name": name, "result": {"error": str(e)}}

async def stream_ollama(
    messages: list[dict],
    model_name: str,
    tools: list[dict] | None = None,
    max_tool_rounds: int = 5,
) -> AsyncGenerator[str, None]:
    """Stream responses from Ollama using the chat API with tool support.

    Emits typed SSE frames:
    - {"type":"text","text":"..."} for model text
    - {"type":"tool_call","id":"...","name":"...","args":{...}} for tool requests
    - {"type":"tool_result","id":"...","result":{...}} for tool results
    - {"type":"error","error":"..."} on failure
    - [DONE] when complete
    """
    emitted_done = False
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {
                "model": model_name,
                "messages": messages,
                "stream": True,
                "options": _ollama_options(),
            }
            if tools:
                payload["tools"] = tools

            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
            ) as response:
                if response.status_code in (400, 404):
                    raise HTTPException(
                        status_code=502,
                        detail=f"Model '{model_name}' not available in Ollama",
                    )
                if response.status_code >= 500:
                    raise HTTPException(status_code=502, detail=f"Ollama error: HTTP {response.status_code}")

                last_content = ""
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError as e:
                        logger.error(f"Unparseable stream line: {line}, error: {e}")
                        if line and not line.startswith("{"):
                            raise RuntimeError(line)
                        continue

                    if data.get("error"):
                        raise RuntimeError(str(data["error"]))

                    if data.get("done", False):
                        msg = data.get("message") or {}
                        if msg.get("tool_calls") and max_tool_rounds > 0:
                            tool_calls = msg["tool_calls"]
                            for tc in tool_calls:
                                tc_id = tc.get("function", {}).get("name", "call_" + str(len(messages)))
                                yield f"data: {json.dumps({'type': 'tool_call', 'id': tc_id, 'name': tc.get('function', {}).get('name', ''), 'args': tc.get('function', {}).get('arguments', {})})}\n\n"

                            tool_results = []
                            for tc in tool_calls:
                                result = await _execute_tool_call(tc)
                                tool_results.append({
                                    "role": "tool",
                                    "content": json.dumps(result["result"]),
                                    "name": result["name"],
                                })
                                yield f"data: {json.dumps({'type': 'tool_result', 'id': tc.get('function', {}).get('name', ''), 'result': result['result']})}\n\n"

                            new_messages = messages + [
                                {"role": "assistant", "content": msg.get("content", ""), "tool_calls": tool_calls}
                            ] + tool_results
                            async for frame in stream_ollama(new_messages, model_name, tools, max_tool_rounds - 1):
                                yield frame
                            return

                        emitted_done = True
                        yield "data: [DONE]\n\n"
                        return

                    msg = data.get("message") or {}
                    if msg.get("role") == "assistant":
                        content = msg.get("content", "") or ""
                        if len(content) > len(last_content):
                            delta = content[len(last_content):]
                            yield f"data: {json.dumps({'type': 'text', 'text': delta})}\n\n"
                            last_content = content
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        if not emitted_done:
            yield "data: [DONE]\n\n"


@app.get("/stream/api/chat")
async def stream_chat(
    message: str,
    model_name: str = "qwen3.5-9b-64k:latest",
    file_ids: Optional[str] = None,
    project_ids: Optional[str] = None,
    messages: Optional[str] = None,
):
    """
    Stream API endpoint using Server-Sent Events (SSE).

    Query params:
    - message: User's prompt
    - model_name: Which Ollama model to use
    - file_ids: Comma-separated uploaded file IDs to include as context
    - project_ids: Comma-separated imported-project IDs — when present, the
      message is RAG-augmented (top relevant chunks from those projects)
    - messages: JSON array of previous {role, content} turns (optional; enables
      multi-turn + tool-call rounds)

    Returns real-time tokens as they're generated by the LLM.
    Frontend receives typed events and appends to display progressively.
    """
    # P7.1: rebuild the full message list for the chat API
    api_messages: list[dict] = [{"role": "system", "content": _system_prompt()}]

    # Previous conversation history (if provided)
    if messages:
        try:
            history = json.loads(messages)
            for m in history:
                if m.get("role") in ("user", "assistant"):
                    api_messages.append({"role": m["role"], "content": m.get("content", "") or ""})
        except json.JSONDecodeError:
            pass

    # Classic flow: selected uploaded/project files concatenated into the prompt.
    ids = [fid.strip() for fid in file_ids.split(",") if fid.strip()] if file_ids else None
    current_message = message
    if ids:
        current_message = add_file_context(current_message, ids)

    # P3.2: project mode — RAG-augment the message with the top relevant chunks.
    prefix = ""
    pids = [p.strip() for p in project_ids.split(",") if p.strip()] if project_ids else []
    if pids:
        prefix, _count = await _rag_context_for_question(pids, current_message)

    current_message = (prefix.rstrip() + "\n\n" + current_message) if prefix else current_message
    api_messages.append({"role": "user", "content": current_message})

    # P7.1: expose registered tools to the model so it can request them
    tools = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for t in TOOL_REGISTRY.values()
    ]

    return StreamingResponse(
        stream_ollama(api_messages, model_name, tools=tools or None),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


async def call_openrouter(prompt: str) -> str:
    """OpenRouter is not shipped in v1.0 — fail cleanly instead of raising raw."""
    raise HTTPException(
        status_code=501,
        detail="OpenRouter support coming in v1.1 — unset OPENROUTER_API_KEY to use your local Ollama models",
    )


@app.get("/api/models")
async def list_models():
    """List available local models from Ollama"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            result = response.json()
            return {
                "models": [m["name"] for m in result.get("models", [])]
            }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Cannot fetch models: {str(e)}")


# ---------------------------------------------------------------------------
# Conversation history (Week 3) — persists chats to local SQLite
# ---------------------------------------------------------------------------
class ChatCreate(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None
    messages: Optional[List[dict]] = None


class ChatUpdate(BaseModel):
    title: Optional[str] = None
    messages: Optional[List[dict]] = None


@app.get("/api/chats")
async def api_list_chats(limit: int = 100):
    return {"chats": database.list_conversations(limit=limit)}


@app.post("/api/chats")
async def api_create_chat(body: ChatCreate):
    chat = database.create_conversation(
        title=body.title, messages=body.messages, model=body.model)
    return chat


@app.get("/api/chats/{chat_id}")
async def api_get_chat(chat_id: str):
    chat = database.get_conversation(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


@app.put("/api/chats/{chat_id}")
async def api_update_chat(chat_id: str, body: ChatUpdate):
    chat = database.update_conversation(
        chat_id, title=body.title, messages=body.messages)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


@app.delete("/api/chats/{chat_id}")
async def api_delete_chat(chat_id: str):
    if not database.delete_conversation(chat_id):
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"ok": True}


@app.get("/api/chats/{chat_id}/export")
async def api_export_chat(chat_id: str, format: str = "md"):
    if format == "json":
        content = database.export_chat_json(chat_id)
        media_type = "application/json"
        filename = f"{chat_id}.json"
    else:
        content = database.export_chat_md(chat_id)
        media_type = "text/markdown"
        filename = f"{chat_id}.md"
    if content is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    import uvicorn
    print("Starting server on http://localhost:8001")
    print("SSE streaming endpoint: /stream/api/chat")
    uvicorn.run(app, host="0.0.0.0", port=8001)
