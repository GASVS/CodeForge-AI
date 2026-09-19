"""
FastAPI backend for Jev Open Source Dashboard.

Week 1 MVP endpoints:
- POST /api/chat — Stream LLM response (Ollama or cloud)
- GET  /api/models — List available models
- GET  /stream/api/chat — SSE streaming for real-time updates
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
import os
from typing import Optional, AsyncGenerator
import json

from contextlib import asynccontextmanager

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
    model_name: Optional[str] = "llama3.2"  # Default Ollama model
    stream: bool = True
    context_code: Optional[str] = None  # For future code-awareness


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


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Main chat endpoint. Routes to Ollama (local) or OpenRouter (cloud).
    
    Supports streaming for real-time feel in UI (use /stream/api/chat for SSE).
    """
    try:
        if not OPENROUTER_API_KEY:  # Default to local Ollama
            response = await call_ollama(request.message, request.model_name)
        else:
            response = await call_openrouter(request.message)
        
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
                buffer = ""
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
async def stream_chat(message: str, model_name: str = "qwen3.5-9b-64k:latest"):
    """
    Stream API endpoint using Server-Sent Events (SSE).
    
    Query params:
    - message: User's prompt
    - model_name: Which Ollama model to use
    
    Returns real-time tokens as they're generated by the LLM.
    Frontend receives events and appends to display progressively.
    """
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
