# Week 1 Checklist — Sept 19-25, 2026

## Goals Foundation + Basic Chat UI Working with Local Models

### Day 1 (Today) — Project Setup ✅

- [x] Create directory structure `~/Desktop/App/jev-opensource-dashboard`
- [x] Write project plan (market research integrated)  
- [x] Draft README.md for GitHub repo
- [x] **Create actual GitHub repository**
  - Public, MIT license
  - Add issue templates (bug report, feature request)
- [x] **Initialize codebase** 
  - Backend: FastAPI + Python venv
  - Frontend: Lovable template / Next.js starter
  - `package.json`, `requirements.txt` files

### Day 2 — Model Integration Test ✅

- [x] Ollama API integration test (`curl http://localhost:11434/api/generate`)
- [x] Basic FastAPI route: `/api/chat` that streams LLM responses
- [x] Error handling for when Ollama isn't running
- [x] Add to docs: "How to install Ollama on Mac/Linux/Windows"

### Day 3 — Frontend Chat UI Skeleton ✅

- [x] Start Lovable UI or Next.js + Tailwind
- [x] Build chat input box (textarea with Send button)  
- [x] Build message display area (user vs AI styling)  
- [x] Basic responsive layout (mobile + desktop)

### Days 4-5 — Connect Frontend to Backend ✅

- [x] API call from React chat UI → FastAPI `/api/chat`
- [x] Streaming responses (SSE or WebSocket for real-time feel)
- [x] Loading states ("AI is typing..." animation)
- [x] Basic markdown rendering in AI responses (`react-markdown`)

### Days 6-7 — Polish + Week 1 Review ✅

- [x] Code highlighting for generated code blocks  
- [x] Copy button on code snippets
- [x] Clear chat history button
- [x] Settings panel stub (model name input, future: API keys)
- [x] **Record demo video** for social media later

---

## Week 1 Deliverables (End of Sept 25)

✅ Working local version where user can:
1. Open http://localhost:3000  
2. Type "explain this code" + paste Python function  
3. Get streaming AI response with syntax highlighting
4. Change which local model is used in settings

---

## Notes  

- **Lovable account status**: [ ] Free tier / [ ] Pro needed?
- **Ollama installed locally**: Yes/No
- **Blocks identified so far**: None yet  
- **Time spent Day 1**: 45 minutes for planning docs
