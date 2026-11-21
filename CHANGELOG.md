# Changelog

All notable changes to CodeForge AI are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned (Phase 6, see `docs/ACTION_PLAN.md`)
- **Multi-model chat with shared history & shared skills** — one conversation, one shared thread + skill set across multiple Ollama models; per-reply model tagging; skills apply identically on any model
- **Code indexer (MCP-style)** — structural code search (definitions, signatures, callers, outlines) with exact `file:line`, exposed as REST + an MCP tool server to replace `grep`/`python` for code browsing

## [1.0.0] — 2026-11-21 · first public release

The "full working app": local-first chat grew into a code-aware, agentic assistant —
project import with RAG, patch application, tool calls, branching, and BYOK cloud models.

### Added
- **Project import + semantic answers (RAG)** — import a folder or zip; files are chunked and embedded on import; `search` top-k endpoint, "semantic answers" toggle, project panel with file tree (`P3.1`, `P3.2`)
- **Code actions** — one-click Explain / Write tests / Find dead code / Refactor chips over any attached file (`P3.3`)
- **Patch generation + apply** — code actions emit unified diffs; Apply writes the file and re-indexes it in RAG (`POST /api/projects/{id}/apply-patch`); structured JSON findings with batch selection for dead-code fixes (`P7.2`, `P7.3`)
- **Tool-call-aware streaming** — `/stream/api/chat` emits typed SSE frames (`text` / `tool_call` / `tool_result` / `error` / `usage`); tool registry executes calls and feeds results back (max 5 rounds); tool-call cards in the UI (`P7.1`)
- **Conversation branching** — branch a thread at any message; lineage marker in the sidebar; both chats persist across refresh (`P7.4`)
- **Token & context awareness** — per-reply token usage with a context-budget bar (warning >80%); long threads auto-summarize oldest turns with an in-chat notice (`P7.5`, `P7.6`)
- **Project-level settings** — per-project temperature + system prompt overriding global defaults (`P7.7`)
- **Prompt templates & slash commands** — reusable skills stored in SQLite; 📝 palette picker or `/name` expansion (`P7.8`)
- **Multimodal input plumbing** — paste/drag image upload, served at `/uploads/`, attached to chat requests as `image_urls` (vision-model ready) (`P7.9`)
- **Git-aware context** — read-only `git-status` / `git-diff` endpoints per project + status panel and diff viewer; the model can answer "what did I change?" (`P7.10`)
- **OpenRouter BYOK** — optional cloud models via your own key (Settings → Cloud); local Ollama stays the default, keys never leave your machine (`P7.12`)
- **Command palette** — ⌘/Ctrl-K for new chat, export, theme/sidebar/logs/settings toggles, project switch (`P7.13`)
- **Robust error UX** — upload failures (413/415/type-filter/backend-unreachable) render as dismissible banners; stream errors land in a styled card with Retry; never a silent hang (`P7.14`)
- **Copy + regenerate** — copy button on every assistant message; "↻ Regenerate" re-sends the last question in the same context (`P7.14`)
- **Persistent history + export** — chats and attached files in local SQLite; export any conversation to Markdown or JSON (`GET /api/chats/{id}/export?format=md|json`)
- **Settings panel** — Ollama status badge, temperature slider, system prompt editor (`P3.4`)
- **Stop button + thinking indicator** for streaming (`P2.3`); live runtime-log drawer in-app
- **Syntax highlighting** — PrismLight with one-dark/one-light themes and line numbers (Phase 4.1)
- **Empty states** — first-conversation card and Ollama-offline card; Esc / ⌘K shortcuts; Enter vs Shift+Enter input handling

### Changed
- Rebranded from "Jev Open Source Dashboard" to **CodeForge AI**; docs rewritten for public launch (`P5.1`)
- Streaming switched from Ollama `/api/generate` to `/api/chat` (multi-turn messages, tool-call support) while staying backward-compatible for text frames

### Security
- Upload hardening: type allow-list + size limits with structured 413/415 errors; tight CORS; path-traversal guards on file reads (`P2.1`, `P2.2`)

### Testing
- Backend pytest suite (isolated temp DB) + frontend vitest + GitHub Actions CI (`P2.4`)
- Playwright E2E smoke tests booting the full stack in Chromium (`P7.11`)

## [0.2.0] — Week 2

### Added
- File upload API (`POST /api/upload`, `GET /api/files`, `GET /api/files/{id}`)
- Code-awareness UI — attach files before asking (explain, debug, write tests on real code)
- Backend injects selected file contents into the prompt for contextual answers

## [0.1.0] — Week 1 · initial release

### Added
- Local-first AI chat UI (React 18 + Vite + Tailwind)
- Streaming responses over Server-Sent Events
- Markdown rendering with syntax-highlighted code blocks and one-click copy
- Model selector with auto-detection of installed Ollama models
- Dark / light theme with persistence
- FastAPI backend on `:8001` with Ollama integration (`:11434`)
- Suggestion prompts, clear-chat, message timestamps

### Notes
- v0.1.0 ships under the initial development name (Jev Open Source Dashboard);
  the project was rebranded to **CodeForge AI** before public launch.
