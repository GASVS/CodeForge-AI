# Jev Open Source Dashboard 🚀

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/yourusername/jev-opensource/blob/main/LICENSE)
[![Build Status](https://img.shields.io/badge/build-in%20progress-yellow.svg)]()

### A privacy-first, open-source AI coding assistant with a beautiful UI. Free alternative to Jev ($400/yr).

**Status**: 🚧 MVP in development — Week 1 (Sept 19-26)  
**Target Launch**: Late October 2026  

---

## 🎯 What This Is

A standalone AI coding assistant that:
- ✅ Works **offline** with local LLMs (Ollama, LM Studio, etc.)
- ✅ Supports **cloud models** (you provide the keys)
- ✅ Respects **privacy**: no telemetry, code stays on your machine by default  
- ✅ Beautiful UI built with modern design tools  
- ✅ **Free and open source** forever

Built because "OpenJev" and similar trending on Hacker News show demand for free alternatives.

---

## 🚦 Quick Start (MVP Phase)

```bash
# Clone repo
git clone https://github.com/yourusername/jev-opensource-dashboard.git
cd jev-opensource-dashboard

# Setup Python environment  
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start local LLM (requires Ollama installed)
ollama pull llama3.2  # or any model you prefer

# Run backend
cd src/backend
uvicorn main:app --reload --port 8000

# Setup frontend (Next.js + Lovable template)
cd ../frontend
npm install
npm run dev

# Open browser
http://localhost:3000
```

---

## 📚 Documentation

| Doc | Purpose |
|-----|---------|
| [Project Plan](docs/project_plan.md) | Complete roadmap, architecture, milestones |
| [Market Research](../market_research_report.md) | Why we're building this (competitive analysis) |
| [Contributing](docs/CONTRIBUTING.md) | How to help |

---

## 🔥 Features (MVP Scope)

### ✅ Core Chat
- Natural language code questions  
- Explain existing codebase files
- Generate functions, tests, docs  
- Syntax highlighting & auto-formatting

### ✅ Model Flexibility  
- Local LLMs (Ollama) - **zero cost, 100% private**  
- Free cloud models (OpenRouter free tier)
- Your own API keys (OpenAI, Anthropic)
- Switch models anytime without restart

### 🚧 Roadmap (v2)  
- GitHub integration for PR reviews
- Team workspaces with collaboration  
- VS Code / JetBrains extensions
- Self-hosted cloud sync for teams

---

## 🛠 Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| **Frontend** | Next.js + React + Shadcn UI + Tailwind | Fast, beautiful UI with Lovable |
| **Backend** | Python FastAPI | Async support, easy LLM integration |
| **Database** | SQLite → PostgreSQL | Local-first scaling later |  
| **Vector DB** | ChromaDB / LanceDB | Semantic code search
| **Models** | Ollama (local), OpenRouter (cloud) | User choice is key |

---

## 🤝 Contributing 

This project needs community help to compete with commercial alternatives. Here's how to contribute:

### For Non-Coders
- 🔴 **Report bugs**: Use GitHub Issues, include steps to reproduce
- 🟢 **Vote on roadmap**: Comment on issues that matter to you  
- 🟡 **Share the word**: Tweet about it, post on HN when we launch

### For Coders
1. Fork repo
2. Create feature branch (`git checkout -b feature/your-feature`)
3. Make changes, add tests if applicable  
4. Commit with meaningful messages
5. Push and open PR

**Priority Areas**:
- UI polish (design feedback)
- Model provider integrations beyond Ollama  
- Mobile-responsive versions
- Test coverage
- Documentation improvements

---

## 📊 Project Status

Current: **Week 1/6 MVP Build** (Sept 19-25, 2026)

| Week | Goal | Status |
|------|------|--------|
| 1 | Foundation + basic chat UI | 🟡 In Progress |
| 2 | Code awareness features | ⚪ Pending |
| 3 | Semantic search + embeddings | ⚪ Pending |
| 4 | Polish + docs | ⚪ Pending |  
| 5-6 | Beta launch | ⚪ Pending |

---

## 🏷️ Why This Exists

Recent Hacker News trends show clear demand:

- **"OpenJev"** launched: 660 points, 277 comments  
- **"Laya open source Jev alternative"**: #1 trending, 398 points
- Multiple discussions about expensive AI tools ($400/yr = out of reach for many)

**Our thesis**: Indie developers want privacy-respecting, free AI coding assistance. Existing open-source tools lack polish. We have the UI advantage (Lovable).

---

## 📜 License

MIT License - see [LICENSE](LICENSE) file.

This project will remain **free and open source**. Monetization (if any) comes from:
- Optional cloud sync add-ons  
- Commercial enterprise hosting  
- Donations via Open Collective

---

## 👥 Community

Join the conversation:
- 💬 **Discord**: [Invite link] (coming soon at launch)  
- 📧 **Email**: your.name@example.com  
- 🐦 **Twitter/X**: @yourhandle (optional, add later)

---

## ❤️ Acknowledgments

Inspired by discussions on Hacker News about affordable AI coding tools. Thanks to:
- Tabby community for open source hosting work
- Continue.dev for proving VS Code extensions can work  
- Every indie developer who's complained about $400/year pricing 😄

---

**Built with ❤️ by a solo developer + Lovable AI**.
