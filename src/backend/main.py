"""
FastAPI backend for Jev Open Source Dashboard.

Week 1 MVP endpoints:
- POST /api/chat — Stream LLM response (Ollama or cloud)
- GET  /api/models — List available models
- GET  /stream/api/chat — SSE streaming for real-time updates
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
import httpx
import os
import time
from typing import Optional, AsyncGenerator, List
import json
import uuid
import shutil
import database

import logging as logging_module

logging_module.basicConfig(level=logging_module.INFO)
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
    # Startup: purge stale uploaded files (> 7 days)
    try:
        removed = 0
        cutoff = time.time() - 7 * 86400
        for entry in os.scandir(UPLOAD_DIR):
            try:
                if time.time_ns() // 1_000_000_000 < cutoff and entry.is_file():
                    os.remove(entry.path)
                    removed += 1
            except OSError:
                pass
        if removed:
            print(f"🧹 Purged {removed} stale upload file(s) from {UPLOAD_DIR}")
    except Exception as e:
        print(f"⚠️ Upload purge failed: {e}")

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
        with open(file_path, "wb") as f:
            f.write(content)

        uploaded_files_store[file_id] = {
            "filename": safe_name,
            "path": file_path,
            "size": total,
            "content": content.decode("utf-8", errors="ignore"),
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
    """Delete an uploaded file"""
    if file_id not in uploaded_files_store:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        os.remove(uploaded_files_store[file_id]["path"])
        del uploaded_files_store[file_id]
        return {"message": "File deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    return {"message": "Jev Open Source Dashboard API", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


def add_file_context(message: str, context_files: List[str]) -> str:
    """Add uploaded file contents to the prompt for code-aware chat"""
    if not context_files:
        return message
    
    file_contents = []
    for file_id in context_files[:5]:  # Limit to 5 files to stay within context window
        if file_id in uploaded_files_store:
            data = uploaded_files_store[file_id]
            content = data["content"]
            filename = data["filename"]
            file_contents.append(f"File: {filename}\n```\n{content}\n```")
    
    if not file_contents:
        return message
    
    context_header = f"\n\nI have the following files for context:\n\n" + "\n\n".join(file_contents)
    return message + context_header


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
                "stream": False,  # Non-streaming for simple endpoint
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
                    "stream": True,  # Enable streaming
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
