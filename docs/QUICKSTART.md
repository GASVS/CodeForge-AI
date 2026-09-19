# 🚀 Quick Start Guide

## Prerequisites

1. **Python 3.11+** (for backend)
2. **Node.js 18+** & npm (for frontend)  
3. **Ollama** installed and running ([download](https://ollama.ai))

## Installation

### 1. Install Ollama models

```bash
# At least one model required
ollama pull qwen2.5:7b   # fast, good quality
# OR
ollama pull llama3.2     # alternative option
```

### 2. Start the Dashboard

Option A — Using startup script (easiest):
```bash
cd ~/Desktop/App/jev-opensource-dashboard
./start.sh
```

Option B — Manual (for debugging):
```bash
# Terminal 1: Backend
cd ~/Desktop/App/jev-opensource-dashboard/src/backend
source ../venv/bin/activate  
uvicorn main:app --reload --port 8001

# Terminal 2: Frontend  
cd ~/Desktop/App/jev-opensource-dashboard/frontend
npm run dev
```

## Access the App

- **Chat interface**: http://localhost:3000 ✅
- **API docs**: http://localhost:8001/docs (Swagger UI)

## Verify Everything Works

Test chat endpoint manually:
```bash
curl -X POST "http://localhost:8001/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, explain what a Python function is", "model_name": "qwen2.5:7b"}'
```

Expected: JSON response with AI explanation

## Common Issues

### Error: "Ollama not responding"
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If blank, start it manually:
ollama serve
```

### Error: "Cannot connect to backend"
```bash
# Kill port 8001 and restart
lsof -ti:8001 | xargs kill -9
# Then restart with ./start.sh
```

### Wrong model detected
Check available models:
```bash
curl http://localhost:8001/api/models
```

Update your selection in Settings sidebar (menu button top-left)

## Next Steps

Week 2 roadmap (not ready yet):
- [ ] Code file upload awareness
- [ ] Syntax highlighting for generated code  
- [ ] Multi-file context window
- [ ] Conversation history persistence

---

**Remember**: Everything runs locally. Your code never leaves your machine.
