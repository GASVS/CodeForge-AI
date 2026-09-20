# Changelog

All notable changes to CodeForge AI are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — v0.3.0 (Week 3)

### Added
- **Persistent conversation history** — chats stored in a local SQLite database; nothing leaves your machine
- Chat management API: `GET/POST /api/chats`, `GET/PUT/DELETE /api/chats/{id}`
- **Export** any conversation to Markdown or JSON (`GET /api/chats/{id}/export?format=md|json`)
- File-context aware streaming chat — attach uploaded files to any message (`file_ids` parameter)
- Code-awareness: upload up to 10 files, AI answers with your code in context

## [v0.2.0] — Week 2

### Added
- File upload API (`POST /api/upload`, `GET /api/files`, `GET /api/files/{id}`)
- Code-awareness UI — attach files before asking (explain, debug, write tests on real code)
- Backend injects selected file contents into the prompt for contextual answers

## [v0.1.0] — Week 1 · initial release

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
