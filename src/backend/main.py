"""
FastAPI backend for Jev Open Source Dashboard.

Week 1 MVP endpoints:
- POST /api/chat — Stream LLM response (Ollama or cloud)
- GET  /api/models — List available models
- GET  /stream/api/chat — SSE streaming for real-time updates
"""

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
import os
from typing import Optional, AsyncGenerator, List
import json
import uuid
import shutil

import logging
logging.basicConfig(level=logging.INFO)

from contextlib import asynccontextmanager

# Temporary storage for uploaded files
UPLOAD_DIR = "/tmp/jev-uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown event handler"""
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

# CORS for frontend (localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production to http://localhost:3000 and domain
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
    """Upload code files for analysis. Returns file IDs that can be referenced in chat."""
    uploaded_files = []
    
    for file in files[:10]:  # Limit to 10 files
        file_id = str(uuid.uuid4())[:8]
        filename = f"{file_id}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        try:
            content = await file.read()
            with open(file_path, 'wb') as f:
                f.write(content)
            
            uploaded_files_store[file_id] = {
                "filename": file.filename,
                "path": file_path,
                "size": len(content),
                "content": content.decode('utf-8', errors='ignore')
            }
            
            uploaded_files.append({
                "id": file_id,
                "filename": file.filename,
                "size": len(content)
            })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload {file.filename}: {str(e)}")
    
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


# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")


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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def call_ollama(prompt: str, model_name: str) -> str:
    """Call local Ollama API (non-streaming)"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,  # Non-streaming for simple endpoint
            }
        )
        
        result = response.json()
        return result.get("response", "No response from model")


async def stream_ollama(prompt: str, model_name: str) -> AsyncGenerator[str, None]:
    """Stream responses from Ollama in real-time"""
    buffer = ""
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
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                chunk = data["response"]
                                buffer += chunk
                                # Yield chunk-by-chunk for better UX
                                yield f"data: {json.dumps({'text': chunk})}\n\n"
                            
                            if data.get("done", False):
                                # Send completion marker
                                yield "data: [DONE]\n\n"
                                return  # Exit generator cleanly
                        except json.JSONDecodeError:
                            continue  # Skip malformed lines
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


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
    """Call OpenRouter API (free/paid models)"""
    # Future implementation: add cloud model support via OpenRouter
    raise NotImplementedError(
        "Cloud model integration coming Week 2. Use Ollama for now."
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


if __name__ == "__main__":
    import uvicorn
    print("Starting server on http://localhost:8001")
    print("SSE streaming endpoint: /stream/api/chat")
    uvicorn.run(app, host="0.0.0.0", port=8001)
