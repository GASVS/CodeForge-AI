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


def _import_project_files(name: str, raw_files: List[dict]) -> dict:
    """Store a project from an already-validated raw file list."""
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
    # Flat project shape (id/name/file_count/total_bytes/files) — same contract
    # as GET /api/projects/{id}; clients (frontend + tests) read `proj["id"]`
    # directly, so don't nest under {"ok", "project"}.
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
        return _import_project_files(name, files)
    if "application/json" in ctype:
        payload = await request.json()
        parsed = _validate_json_files(payload)
        return _import_project_files(parsed[0]["name"], parsed[0]["files"])
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


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Main chat endpoint with optional file context"""
    try:
        # Add file context if uploaded files are provided
        enhanced_message = request.message
        model_to_use = request.model_name or "qwen3.5-9b-64k"
        if request.context_files:
            enhanced_message = add_file_context(request.message, request.context_files)
        
        if not OPENROUTER_API_KEY:  # Default to local Ollama
            response = await call_ollama(enhanced_message, model_to_use)
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


async def call_ollama(prompt: str, model_name: str) -> str:
    """Call local Ollama API (non-streaming).

    Raises HTTPException(502) if the model is unknown or Ollama errors,
    instead of letting Ollama's error payload surface as a fake 200.
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "system": _system_prompt(),
                "stream": False,  # Non-streaming for simple endpoint
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
        return result.get("response", "")


async def stream_ollama(prompt: str, model_name: str) -> AsyncGenerator[str, None]:
    """Stream responses from Ollama in real-time.

    Errors (unknown model, Ollama down, 5xx) are delivered as a single
    SSE `error` frame followed by `[DONE]`, so the frontend can render an
    error card instead of hanging on an empty stream.
    """
    emitted_done = False
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "system": _system_prompt(),
                    "stream": True,  # Enable streaming
                    "options": _ollama_options(),
                }
            ) as response:
                if response.status_code in (400, 404):
                    raise HTTPException(
                        status_code=502,
                        detail=f"Model '{model_name}' not available in Ollama",
                    )
                if response.status_code >= 500:
                    raise HTTPException(status_code=502, detail=f"Ollama error: HTTP {response.status_code}")

                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if data.get("error"):
                                raise RuntimeError(str(data["error"]))
                            chunk = data.get("response")
                            if chunk:
                                yield f"data: {json.dumps({'text': chunk})}\n\n"
                            if data.get("done", False):
                                emitted_done = True
                                yield "data: [DONE]\n\n"
                                return
                        except json.JSONDecodeError as e:
                            # Ollama may send a plain-text error line; surface it
                            logger.error(f"Unparseable stream line: {line}, error: {e}")
                            if line and not line.startswith("{"):
                                raise RuntimeError(line)
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        if not emitted_done:
            yield "data: [DONE]\n\n"


@app.get("/stream/api/chat")
async def stream_chat(
    message: str,
    model_name: str = "qwen3.5-9b-64k:latest",
    file_ids: Optional[str] = None,
):
    """
    Stream API endpoint using Server-Sent Events (SSE).

    Query params:
    - message: User's prompt
    - model_name: Which Ollama model to use
    - file_ids: Comma-separated uploaded file IDs to include as context

    Returns real-time tokens as they're generated by the LLM.
    Frontend receives events and appends to display progressively.
    """
    # Inject selected uploaded files into the prompt
    ids = [fid.strip() for fid in file_ids.split(",") if fid.strip()] if file_ids else None
    if ids:
        message = add_file_context(message, ids)

    return StreamingResponse(
        stream_ollama(message, model_name),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",  
            "X-Accel-Buffering": "no"  # Disable nginx buffering
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
