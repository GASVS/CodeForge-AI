# CodeForge AI — Detailed Action Plan (2026-09-20)

> **Rule of this file:** every task has **Steps → Verify → Done when**.
> Log each completed task in `SESSION_LOG.md` *immediately* (the app crashes; one task = one log entry).
> Work top-to-bottom. A phase is done only when every "Done when" box is checked.
>
> **Start here — current breakage (verified 2026-09-20):**
> 1. `frontend/src/App.tsx` is a 66-line stub (live Vite entry). Working 487-line version exists at git `b90c6ae:frontend/src/App.tsx`.
> 2. `src/backend/main.py:20` `from . import database` → `uvicorn main:app` crashes (ImportError). `start.sh` is broken.
> 3. No `.gitignore` (deleted in `6b07a3f`). `private/`, `frontend/.env.local`, `codeforge.db*`, venvs are one `git add .` away from being committed.
> 4. `frontend/components/ChatSidebar.tsx` imports `@/types/chat` (file doesn't exist) → build of any tree that renders it fails.

---

## Phase 0 — Repo safety (do FIRST, before any feature work)

### 0.1 Restore `.gitignore` — ✅ DONE 2026-09-20 (also moved .env.local + codeforge.db* into `private/runtime/`, `database.py` DB_PATH repointed & verified)
- [ ] Step: create `.gitignore` at repo root:
  ```
  private/
  .env
  .env.local
  *.env
  venv/
  src/backend/venv/
  frontend/venv/
  node_modules/
  dist/
  frontend/dist/
  *.db
  *.db-shm
  *.db-wal
  __pycache__/
  .pytest_cache/
  .next/
  *.log
  ```
- [ ] Verify: `git status --short` shows none of `private/`, `.env.local`, `codeforge.db*`, `node_modules/`, `venv/`, `dist/`.
- **Done when:** `git add -A && git status --short` lists ZERO env/db/venv/node_modules entries. Commit: `chore: restore .gitignore (secrets + runtime artifacts)`.

### 0.2 Fix backend import so `start.sh` works again — ✅ DONE 2026-09-20 (server now boots via `uvicorn main:app`; all endpoints exercised, see A6 in SESSION_LOG)
- [ ] Step: `src/backend/main.py` line 20: `from . import database` → `import database`.
- [ ] Verify 1: `cd src/backend && ../../venv/bin/python -c "import main"` → no ImportError.
- [ ] Verify 2: start uvicorn on :8001, `curl localhost:8001/health` → `{"status":"healthy"}`, `curl localhost:8001/api/chats` → `{"chats":[...]}`, then kill it.
- [ ] Verify 3: `./start.sh` boots backend + frontend without a manual kill (check :8001 + :3000 both respond).
- **Done when:** `start.sh` brings both services up from a cold terminal. Commit: `fix: relative import broke uvicorn main:app startup`.

### 0.3 Decide the frontend tree (one app, not two)
- [x] Step: **Decision: keep the Vite app** (`frontend/src/` + `frontend/components/`). `app/` (Next-style) cannot build — no `next` dependency — and would duplicate everything.
- [ ] Step: move the good parts of `frontend/app/page.tsx` into the Vite app in P1 (do NOT delete in this phase — recover first).
- [ ] Step: remove `frontend/frontend/` (nested junk: 1 jest test + package.json). Keep the test only if it still applies — port it to `frontend/src/__tests__/`.
- [ ] Verify: `git log --oneline -- frontend/app/page.tsx` confirmed — the tree is git-tracked, so deletion is recoverable; still, commit first.
- **Done when:** `frontend/` contains exactly one build entry: `index.html → src/main.tsx → src/App.tsx`.

### 0.4 Fix `build.sh`
- [ ] Step: current script runs `pytest` (empty tests dir → meaningless) and `cp -r dist/* ../dist/` (broken paths). Rewrite:
  1. `pip install -r src/backend/requirements.txt` (in root venv)
  2. `pytest tests/ -q` (remove `|| true` once tests exist; keep `--collect-only` check for now)
  3. `cd frontend && npm ci && npm run build`
  4. `rm -rf dist/ && cp -r frontend/dist dist/`
- [ ] Verify: `./build.sh` exits 0 and `dist/index.html` exists.
- **Done when:** build script green + artifact present. Commit: `build: fix script paths, remove masked pytest`.

---

## Phase 1 — Restore the working chat app (target: chat streaming E2E again)

### 1.1 Recover the full App.tsx — ✅ DONE 2026-09-20 (restored from b90c6ae, tsc clean; plus start.sh:33 unclosed-quote bug fixed)
- [ ] Step: `git show b90c6ae:frontend/src/App.tsx > frontend/src/App.tsx` (487 lines: streaming chat, FileContext panel, markdown rendering, model selector, theme).
- [ ] Step: `npx tsc --noEmit` in `frontend/`. Fix any missing pieces it reports (e.g. `../components/SettingsPanel` path — the real components live in `frontend/components/`, so from `src/App.tsx` the import is `../components/...` ✅; check `./FileContext` resolves).
- [ ] Verify: `npx tsc --noEmit` clean.
- **Done when:** tsc clean. Commit: `restore: working App.tsx from b90c6ae (stub regression)`.

### 1.2 Verify Week-1/2 flows work end-to-end — ✅ DONE at API level 2026-09-20 (A7.2: boot via start.sh, upload+stream E2E through vite :3000 proxy, restored app confirmed served; browser-rendering visual pass still recommended)
- [ ] Step: with backend + Ollama up (P0.2 verified), `./start.sh`, open http://localhost:3000.
- [ ] Test A (chat): type a question → tokens stream in progressively (not a 30 s freeze).
- [ ] Test B (model): Settings → pick `qwen3.5-9b-64k:latest` → response uses it; `qwen3.8-27b-96k:latest` also works.
- [ ] Test C (files): drag in a small `.py` → check it → ask "what does greet do?" → model references the file content. (Backend E2E for this already passed at `b90c6ae`; this re-proves the restored frontend sends `file_ids`.)
- [ ] Verify C in network panel: `GET /stream/api/chat?...&file_ids=...` returns 200.
- **Done when:** A/B/C all pass against the LIVE frontend (curl is not enough). Log to SESSION_LOG.

### 1.3 Wire ChatSidebar (Week-3 frontend)
- [ ] Step: create `frontend/types/chat.ts` (the missing `@/types/chat`): export `interface Chat { id, title, model, created_at, updated_at, message_count }`.
- [ ] Step: add tsconfig `paths`: `"@/*": ["./src/*"]` — check `frontend/tsconfig.json` first; if `@` should map to the frontend root, point it there instead so `frontend/components` and `frontend/types` both resolve. Alternatively switch imports in ChatSidebar to relative paths. Choose ONE and apply consistently.
- [ ] Step: in `App.tsx` add: chats list state; on mount `fetch /api/chats`; "New chat" → `POST /api/chats`; select → `GET /api/chats/{id}` and render its messages; delete → `DELETE`; on every turn finished, `PUT /api/chats/{id}` with the message array (persist!); "Export" button → open `/api/chats/{id}/export?format=md`.
- [ ] Verify: send 3 messages → refresh page → conversation still there (came from SQLite, not localStorage).
- [ ] Verify: create 2 chats, see both in sidebar, delete one, survives refresh.
- **Done when:** refresh-survival test passes. Commit: `feat: chat history sidebar wired to SQLite backend`.

### 1.4 Delete the dead tree
- [ ] Step: now that P1.3 is done, delete `frontend/app/` (page.tsx, layout.tsx, globals.css) and `components/FileUploader.tsx` (superseded by `src/FileContext.tsx`) — ONLY if nothing in the Vite app imports them (grep first).
- [ ] Step: remove duplicate CSS trees: keep one globals approach; delete the rest.
- [ ] Verify: `npm run build` clean; search for `@/components` / `app/` imports → none.
- **Done when:** build green, single CSS tree, tree matches `SESSION_LOG` "live entry" description. Commit: `chore: remove dead Next-style tree + duplicate uploader`.

---

## Phase 2 — Hardening (privacy + robustness; before anything public)

### 2.1 Upload hardening (backend)
- [ ] Max size: read in chunks, reject > 2 MB/file (HTTP 413), reject > 10 files/request (already 10, but enforce size).
- [ ] Extension allow-list (code/text: py js ts jsx tsx rb go rs java c cpp h md json yml yaml toml sh html css cssx vue svelte) + text sniff (binary → 415).
- [ ] Replace unbounded in-memory `uploaded_files_store` dict with SQLite table `uploads(id, filename, size, content, created_at)`; cap per-user total 20 files; cleanup endpoint already exists (`DELETE /api/files/{id}`) — add startup purge of files > 7 days old.
- [ ] `UploadedFile.filename` → sanitize (basename only, no path traversal — currently `f"{file_id}_{file.filename}"` is OK, but strip any `/` just in case).
- [ ] CORS: `allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"]` (configurable via env `ALLOWED_ORIGINS` for prod domains).
- [ ] Add `GET /api/files/{id}` size cap: refuse to return content > 256 KB in the list endpoint (content endpoint OK).
- [ ] Verify: upload a 3 MB file → 413. Upload a PNG named `.txt` → 415. Restart backend → previous valid uploads still listed.
- **Done when:** all four checks pass. Commit: `security: upload limits, allow-list, DB-backed store, tight CORS`.

### 2.2 OpenRouter either works or fails cleanly
- [ ] Option A (recommended for v1): delete the `OPENROUTER_API_KEY` branch; `POST /api/chat` always routes to Ollama. Keep env var documented as "coming soon" in README. → Zero risk.
- [ ] Option B (if shipping): implement `call_openrouter` properly (chat-completions, streaming via SSE, 501 with a clear message if model unknown), add unit test with a mocked httpx transport.
- [ ] Verify: with `OPENROUTER_API_KEY=garbage` set, `/api/chat` returns a clean 501/400 — never a raw 500 traceback (or the env var simply doesn't affect routing, Option A).
- **Done when:** no code path from `/api/chat` raises an unhandled `NotImplementedError`.
- [ ] **Also (audit finding 2026-09-20):** `call_ollama` swallows Ollama 404 (unknown model) → returns HTTP 200 + `"No response from model"`. Fix: check `response.status_code` after `resp = await client.post(...)`, raise `HTTPException(502, f"Model '{model_name}' not available in Ollama")` on 404/5xx. Verify: `/api/chat` with `no-such-model` → 502 with that message.

### 2.3 Streaming robustness
- [ ] Frontend: detect "thinking" stalls on qwen3.8-thinking models (no `text` in the first 3 s) → show `Thinking…` with an animated dot; abort after 120 s with an error card (currently it can hang with an empty bubble).
- [ ] Frontend: **Stop button** → `eventSource.close()` mid-stream, keep partial text (check `App.tsx` at b90c6ae — add if missing).
- [ ] Backend: send `data: {"error": ...}` on mid-stream Ollama failure so the UI can render a red card instead of frozen spinner (partly done — verify the client handles `error` and `[DONE]`).
- [ ] Verify: start a long generation, click Stop inside 5 s → partial text kept, spinner gone, can send next message.
- **Done when:** stop-test + error-test pass.

### 2.4 Tests + CI
- [ ] Backend tests in `tests/` (FastAPI `TestClient`, Ollama mocked so no model needed): health, models-503 path, chats CRUD round-trip, chat-export md/json, upload size-limit + 415, stream error-frame.
- [ ] `src/backend/requirements.txt` + `requirements-dev.txt` (pytest, httpx already there, pytest-asyncio; chromadb stays commented for P3).
- [ ] Frontend: 1 component test (port the existing `MessageInput.test.tsx` from `frontend/frontend/` into the Vite app with Vitest — swap jest config for `vitest` in package.json, or keep jest with jsdom; pick Vitest for Vite-native simplicity).
- [ ] `.github/workflows/ci.yml`: job 1 python 3.11 `pip install -r requirements.txt -r requirements-dev.txt && pytest -q`; job 2 node 20 `npm ci && npx tsc --noEmit && npm run build && npm test`.
- [ ] Verify: `pytest -q` local passes; push a branch, CI goes green.
- **Done when:** local + CI both green. Commit: `test: backend API tests, vitest setup, CI workflow`.

---

## Phase 3 — Code-aware core (the real differentiator)

### 3.1 Folder import (whole-project context, not single files)
- [ ] Backend: `POST /api/projects` (multipart directory or zip) → walk with size/symlink guards (skip node_modules, .git, venv, >2 MB files, non-allowlisted extensions) → store tree in SQLite `projects` + `project_files` tables, return tree JSON.
- [ ] Frontend: file-tree panel (expand/collapse), per-file "add to context" checkbox + "Add all (respecting caps)".
- [ ] Verify: import a real repo (this repo) → tree renders; asking a question with 5 selected files produces an answer that cites file paths.

### 3.2 Semantic search (RAG)
- [ ] Backend: chunk project files (~200 tokens, 20 overlap), embed via Ollama (`/api/embeddings` with a local embedding model — test which one is installed or `ollama pull nomic-embed-text`), store in SQLite `embeddings` table; `GET /api/projects/{id}/search?q=&k=10` cosine-top-k (numpy is fine; no ChromaDB needed for this scale — drop the ChromaDB dep from the plan).
- [ ] Frontend: search box in the file panel ("Where is X defined?") → top-k snippets with file:line; answer-question flow auto-injects top-k as context (replace naive concat in `add_file_context` with RAG-picked context).
- [ ] Verify: ask "where is add_file_context defined" → correct file + lines in < 3 s.

### 3.3 Code actions (v1 set, keep it to four)
- [ ] "Explain this file" — prompt template + context = that file → answer with inline references.
- [ ] "Generate unit test" — context = file → answer in a code block with a copy button (copy button exists on markdown blocks — verify).
- [ ] "Find dead code / unused imports" — context = selected files.
- [ ] "Refactor to follow this pattern" — free text + selected files.
- [ ] All actions: one-click chips above the input bar; record the action + context in the stored chat so history stays meaningful.
- [ ] Verify: each chip works against a sample file; results saved on refresh.

### 3.4 Model & provider settings (close the plan's Phase 1.2)
- [ ] Settings panel: Ollama base URL (env `OLLAMA_API_URL` already exists — expose read-only status: up/down + model count), default model picker, system prompt field (stored in SQLite `settings`), temperature slider (backend: add `options: {temperature}` to Ollama call — currently missing).
- [ ] OpenRouter: still option A from 2.2 → show "coming in v1.1" disabled row. (Don't ship a dead control.)
- [ ] Verify: change system prompt → new chats use it; old ones unaffected.

---

## Phase 4 — UX polish

- [ ] **Code highlighting in responses:** `react-markdown` already renders; add `remark-gfm` tables (dep present) + `react-syntax-highlighter` (Prism light) theme-matched to light/dark. Verify: a Python code block shows colors in both themes.
- [ ] **Empty states:** no chats yet → "Start your first conversation" card with the 4 action chips; no model → "Ollama offline" card with a button that POSTs `ollama pull qwen3.5:9b`… (no — keep it copy-safe: show the exact command in a code block, no execution).
- [ ] **Keyboard:** Enter=send, Shift+Enter=newline (verify), `Ctrl/Cmd+K` → focus search box (file-panel search), `Esc` closes settings.
- [ ] **Responsive:** ≤768 px → sidebar collapses to a drawer; file panel toggles like on mobile. Verify at 390 px and 1440 px widths.
- [ ] **Error cards everywhere:** 503 Ollama-down, 413 too big, 415 bad type, stream errors → styled red cards with a "retry" action; never a silent hang or a bare traceback string in a chat bubble.
- [ ] **Copy + feedback:** copy button on every assistant message; "regenerate last answer" button (keep same context).
- [ ] Verify: run a 10-minute dogfood session, log every friction point in SESSION_LOG; fix top 3.

---

## Phase 5 — Docs + launch (v1.0)

### 5.1 Docs pass
- [ ] `README.md` rewrite (public): 1-line pitch · screenshot/GIF · 3-command quick start (install Ollama + model, `./start.sh`, open :3000) · feature table · architecture mini-diagram · security/privacy section (local-first, what's stored where: SQLite + `~/.cache` uploads) · roadmap (link ACTION_PLAN) · license (MIT — verify LICENSE header name).
- [ ] `docs/QUICKSTART.md` + `CONTRIBUTING.md` still accurate against final tree.
- [ ] Delete/archive stale state files: `mvp_report.md`, `project_status_resume.md`, `WEEK1_COMPLETE.md`, `WEEK2_COMPLETE.md`, `day1_progress.md`, `week1_checklist.md`, `week2_progress.md` → move to `docs/archive/` (history stays in git + SESSION_LOG).

### 5.2 Launch assets
- [ ] Demo GIF: 30 s — open app → import this repo → RAG question → code-gen answer. (Record with OBS; trim.)
- [ ] Screenshot set (dark + light) for README.
- [ ] `CHANGELOG.md` final v1.0 entry; tag `v1.0`.
- [ ] GitHub: issue templates (bug/feature), Discussions or Discord invite, "good first issue" labels on 3 items (suggestion: temperature slider 3.4, Stop button if still open 2.3, copy on code blocks).
- **Done when:** README renders on GitHub with working quickstart (verify on a fresh container: clone → start.sh → chat works).

### 5.3 Launch (after 5.1+5.2 green)
- [ ] Product Hunt (schedule off-peak day), HN ("Show HN" — quiet Tuesday/Thursday morning), IndieHackers, X outreach to 20 (drop the 50-target to protect quality).
- [ ] Post-launch: 48 h bug triage window → patch release v1.0.1.

---

## Backlog (v1.1+, NOT in the v1 path)
- OpenRouter + OpenAI/Anthropic BYOK (real impl of 2.2-Option-B)
- GitHub OAuth for settings sync (plan Phase 1.3)
- Terminal integration (plan Phase 3.3) — sandbox design review first
- Command palette (Cmd+K) — becomes "focus search" in v1
- Multi-user / team workspaces
- E2E test harness (Playwright) for the browser flows
- Postgres option for shared deployments
- i18n, a11y audit (WCAG AA), Lighthouse ≥ 95

---

## Definition of Done — v1.0 (the "full working app")
- [ ] `./start.sh` from a clean clone → working chat in < 2 min (no manual steps)
- [ ] Streaming chat with working Stop button + thinking indicator
- [ ] File upload + folder import + RAG search answering correctly
- [ ] Chat history persists across refresh (SQLite-sourced) + export
- [ ] `pytest` + `tsc` + `npm build` + CI all green
- [ ] No `.env`/db/venv in `git status`; `.gitignore` enforced
- [ ] README quickstart verified on a fresh machine
- [ ] Zero unhandled 500s on any documented endpoint (tested with bad inputs)
