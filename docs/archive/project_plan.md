# Jev Open Source Dashboard (CodeForge AI) — Project Plan

**Status**: In development — Week 3+ (frontend regression in repair)
**Target MVP**: 4–6 weeks (revised: see `docs/ACTION_PLAN.md`)
**Actual Tech Stack**: React 18 + Vite 5 + TypeScript + Tailwind (frontend) · Python 3.11 FastAPI + SQLite (backend) · Ollama (local LLMs)

> ⚠️ **Earlier versions of this plan said "Next.js + Lovable". The repo never used either.**
> `frontend/package.json` has no `next` dependency; the live entry is Vite (`frontend/src/main.tsx → src/App.tsx`, dev port 3000, proxy `/api` → backend :8001).
>
> **Documentation map (single source of truth per audience):**
> - Day-to-day state + crash recovery: **`SESSION_LOG.md`**
> - Step-by-step next work: **`docs/ACTION_PLAN.md`**
> - Public-facing: **`README.md`** (rewrite needed — currently a copy of this plan)
> - Strategy: this file.

---

## Executive Summary

Build a polished, open-source alternative to Jev ($400/yr AI coding assistant) powered by local LLMs (Ollama) with a clean, fast web UI. Users keep full control: model choice, their own API keys, code never leaves the machine.

**Key differentiator**: Privacy-first local-first design, zero cost, user-controlled models, and a UI that makes self-hosted tools feel finished.

---

## Market Validation (Completed)

- ✅ "OpenJev" trending #28 on Hacker News: 660 points, 277 comments
- ✅ "Laya the open source version of Jev" at #1: 398 points, 89 comments
- ✅ Multiple discussions about expensive AI tools → demand for alternatives

**Signal**: High. Real market pull, not push.

---

## Reality Check — verified against the code, 2026-09-20

### Backend `src/backend/` — Weeks 1–3 features are DONE ✅ (one startup bug, one dead path)

| Capability | Endpoints | Status |
|---|---|---|
| Health check | `GET /health` | ✅ |
| Model listing (Ollama) | `GET /api/models` | ✅ |
| Non-streaming chat | `POST /api/chat` | ✅ |
| **SSE streaming chat** | `GET /stream/api/chat` (+ `file_ids` context) | ✅ E2E-verified at commit `b90c6ae` |
| Multi-file upload | `POST /api/upload`, `GET/DELETE /api/files[/{id}]` | ✅ (hardening gaps below) |
| File-context injection | `add_file_context()` | ✅ works (naive prompt concat) |
| **Conversation persistence** | `GET/POST /api/chats`, `GET/PUT/DELETE /api/chats/{id}` | ✅ SQLite via `database.py` |
| **Chat export** | `GET /api/chats/{id}/export?format=md\|json` | ✅ |
| Cloud models (OpenRouter) | `call_openrouter()` | ❌ raises `NotImplementedError` → HTTP 500 if `OPENROUTER_API_KEY` is set |
| Auth / GitHub OAuth (plan Phase 1.3) | — | not started (deferred) |

**Blocking bug (verified by import test):** `main.py:20` — `from . import database` is a relative import in a module run as top-level `main`. **`uvicorn main:app` (i.e. `start.sh`) crashes with `ImportError: attempted relative import with no known parent package`.** Fix: `import database`.

**Hardening gaps** (contradict the privacy posture if published as-is): CORS `allow_origins=["*"]`; uploads have no size limit, content is kept in an unbounded in-memory dict + `/tmp/jev-uploads` with no cleanup; `tests/` is empty; `build.sh` hides failures with `pytest … || true`.

### Frontend — split-brain; live entry is a stub ❌ (regression)

| Artifact | State |
|---|---|
| `frontend/src/App.tsx` (live Vite entry) | **66-line stub at HEAD**: theme toggle + a textarea that `console.log`s. No chat, no API calls. The full 487-line working version (streaming chat, FileContext panel, markdown rendering, model selector) survives in git at `b90c6ae:frontend/src/App.tsx`. |
| `frontend/app/page.tsx` (Next-style tree) | 286-line chat UI — the **most complete frontend in the repo** (chat list, FileUploader, Settings) — but **unbuildable**: no Next.js dependency anywhere, and it + `components/ChatSidebar.tsx` import `@/types/chat`, a module **that does not exist**. |
| `frontend/components/` | MessageList, MessageInput, SettingsPanel, FileUploader, ChatSidebar (broken import) — Vite-compatible with fixes |
| `frontend/src/FileContext.tsx` | Working Week-2 drag-and-drop upload panel — only rendered by the lost 487-line App |
| `frontend/frontend/` | Nested duplicate (jest test + package.json) — junk |
| Duplication | Two app shells (`src/App.tsx` vs `app/page.tsx`), two uploaders (FileContext vs FileUploader), three CSS trees (`app/globals.css`, `src/globals.css`, `src/index.css`) |

### Repo hygiene ❌

- **No `.gitignore`** (deleted in commit `6b07a3f`). Untracked but on disk: `private/`, `frontend/.env.local`, `src/backend/codeforge.db*`, 3× `venv/`, `node_modules/`, `dist/`. Any `git add .` commits secrets + a local DB.
- `tests/` empty; `build.sh` has broken path logic (`cp -r dist/* ../dist/`).
- Docs badly out of date — drift map below.

### Docs drift map

| Doc | Claims | Reality |
|---|---|---|
| `README.md` | Copy of this plan, "Planning Phase" | App is mid-Week-3; README must be its own public doc |
| `docs/mvp_report.md` | "No streaming", "Next.js 14", "no file upload" | Streaming ✅, file upload ✅, stack is Vite |
| `docs/project_status_resume.md` | "Week 2, Vite chat E2E ✅, Next.js 14" | Was true at `b90c6ae`, then **regressed**; no Next.js anywhere |
| `SESSION_LOG.md` | Week 3 = TODO | Week-3 **backend is done**; chat sidebar exists but dead; log predates the App.tsx regression |

---

## Consolidated Roadmap (done / remaining)

| # | Milestone | Backend | Frontend | Status |
|---|---|---|---|---|
| W1 | Chat UI + Ollama streaming | ✅ | 🔴 regressed to stub | restore (ACTION_PLAN P1) |
| W2 | File upload + code-aware chat | ✅ E2E proven | 🟡 code exists (FileContext) but not wired into live entry | rewire (P1.3) |
| W3 | Persistence: store, sidebar, export | ✅ + SQLite | 🟡 `ChatSidebar.tsx` exists w/ broken import | wire (P1.4) |
| W4 | Code-aware core: folder import, file tree, semantic search (RAG) | ⬜ | ⬜ | P3 |
| W5 | UX polish: highlighting, stop button, empty states, responsive | — | — | P4 |
| W6 | Launch: README, demo, issue templates, PH/HN, v1.0 | CI ✅ needed | — | P5 |

**Ordered, verifiable steps for every remaining item: [`docs/ACTION_PLAN.md`](./ACTION_PLAN.md).**

---

## Competitive Analysis

### Jev (target market leader)

| Aspect | Jev | Our angle |
|--------|-----|-----------|
| Price | $400/year | Free + optional donations |
| Platform | VS Code extension | Standalone web app + extensions later |
| AI provider | Proprietary/cloud | User choice (local + cloud keys) |
| Privacy | Cloud processing | Local-first by default, zero telemetry |
| UI/UX | Functional | Clean, fast, focused |

**Winning strategy**: better UX + privacy + free = viral loop in the indie-dev community.

### Existing open-source / commercial alternatives

| Tool | Strengths | Weaknesses | How we beat them |
|------|-----------|------------|------------------|
| **Cursor** | Great UI, Claude integration | Freemium limits, cloud-first | Local first, unlimited |
| **Continue.dev** | Open source, powerful | Extension-only, setup-heavy | Out-of-the-box web app |
| **Tabby** | Self-hosted, local models | Raw UX | Modern UX |
| **Codeium** | Fast, free tier | Proprietary | Transparency |

---

## Technical Architecture (as-built + planned)

```
┌─────────────────────────────────────────┐
│   Frontend (React 18 + Vite 5 + TS)     │
│   Chat UI · File panel · Chat sidebar   │
│   Settings · Themes                     │
└──────────────┬──────────────────────────┘
               │ HTTP + SSE (:3000 dev proxy → :8001)
┌──────────────▼──────────────────────────┐
│      Backend (FastAPI, Python 3.11)     │
│  Model provider layer: Ollama ✅        │
│              OpenRouter ❌ (TODO)        │
│  File-context store (uploads → prompt)  │
│  Conversation store (SQLite, database.py)│
└──────────────┬──────────────────────────┘
               │ localhost:11434
┌──────────────▼──────────────────────────┐
│   Ollama (local models)                 │
│   qwen-family, 100% offline             │
└─────────────────────────────────────────┘

Planned, not built: code indexing + local
vector search (RAG); Postgres option; auth.
```

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| **Overscoping** | High | Critical | Strict MVP scope; ACTION_PLAN phases are the gate |
| **Docs/code drift (recurring!)** | Confirmed | High | One owner per doc type (map above); update `SESSION_LOG.md` every action |
| **Frontend split-brain (2 app shells)** | Confirmed | High | P1 collapses to one Vite app; dead tree deleted |
| **Secrets leak on publish (no .gitignore)** | High | Critical | ACTION_PLAN 0.1 — **before any push** |
| **LLM costs** | Medium | Medium | Default local; OpenRouter optional via user key |
| **Privacy concerns** | High | Critical | Local-first; CORS+upload hardening (P2) before public push |
| **Qwen "thinking" models stall streams** | Confirmed | Medium | "Thinking…" UI state + long timeouts (P2.4) |

---

## Success Metrics (First 90 Days)

| Metric | Target | Measurement |
|--------|--------|-------------|
| GitHub stars | 100+ | Repo analytics |
| Active users (daily) | 50+ | Opt-in anonymous count (none by default) |
| Community | 200+ | Discord |
| Product Hunt upvotes | 200+ | Launch day |
| HN engagement | 50+ comments | HN API |

---

## Monetization Strategy (Post-MVP)

**Phase 1**: Free, open source, no telemetry.
**Phase 2** (Month 4+): optional paid — cloud sync ($5/mo), team workspaces ($49/mo), priority model integrations, donations via Open Collective.

> Philosophy: *Monetize convenience, not capability. Core stays free forever.*

---

## Timeline (revised around ACTION_PLAN phases)

| Phase | Work | Target |
|-------|------|--------|
| P0 — Repo safety | `.gitignore`, startable backend, frontend-tree decision | Day 1 |
| P1 — Restore working app | Vite app back (from `b90c6ae`), ChatSidebar wired, dead code deleted, E2E green | Days 1–2 |
| P2 — Hardening | Upload limits, CORS, OpenRouter graceful failure, streaming robustness, tests, CI | Days 3–5 |
| P3 — Code-aware core | Folder import, file tree, embeddings search (RAG), code actions | Days 6–10 |
| P4 — UX polish | Code highlighting pass, stop/streaming UX, empty states, responsiveness | Days 10–12 |
| P5 — Launch | README, demo, issue templates, PH/HN, v1.0 tag | Days 12–15 |

---

## Notes from Market Research

1. **"Too expensive"** → free open source solves this immediately
2. **"Privacy concerns with cloud AI"** → local-first by default
3. **"UI feels clunky/outdated"** → clean, fast, focused UI
4. **"No control over models"** → full choice of model + provider

Launch hook: *"Finally, an AI coding assistant that respects your privacy and your wallet."*
