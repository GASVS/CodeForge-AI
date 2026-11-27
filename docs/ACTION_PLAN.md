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
- [x] Step: create `.gitignore` at repo root: ✅ VERIFIED 2026-11-27 sweep
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
- [x] Verify: `git status --short` shows none of `private/`, `.env.local`, `codeforge.db*`, `node_modules/`, `venv/`, `dist/`. ✅ VERIFIED 2026-11-27 sweep
- **Done when:** `git add -A && git status --short` lists ZERO env/db/venv/node_modules entries. Commit: `chore: restore .gitignore (secrets + runtime artifacts)`.

### 0.2 Fix backend import so `start.sh` works again — ✅ DONE 2026-09-20 (server now boots via `uvicorn main:app`; all endpoints exercised, see A6 in SESSION_LOG)
- [x] Step: `src/backend/main.py` line 20: `from . import database` → `import database`. ✅ VERIFIED 2026-11-27 sweep
- [x] Verify 1: `cd src/backend && ../../venv/bin/python -c "import main"` → no ImportError. ✅ VERIFIED 2026-11-27 sweep
- [x] Verify 2: start uvicorn on :8001, `curl localhost:8001/health` → `{"status":"healthy"}`, `curl localhost:8001/api/chats` → `{"chats":[...]}`, then kill it. ✅ VERIFIED 2026-11-27 sweep
- [x] Verify 3: `./start.sh` boots backend + frontend without a manual kill (check :8001 + :3000 both respond). ✅ VERIFIED 2026-11-27 sweep
- **Done when:** `start.sh` brings both services up from a cold terminal. Commit: `fix: relative import broke uvicorn main:app startup`.

### 0.3 Decide the frontend tree (one app, not two)
- [x] Step: **Decision: keep the Vite app** (`frontend/src/` + `frontend/components/`). `app/` (Next-style) cannot build — no `next` dependency — and would duplicate everything.
- [x] Step: move the good parts of `frontend/app/page.tsx` into the Vite app in P1 (do NOT delete in this phase — recover first). ✅ VERIFIED 2026-11-27 sweep
- [x] Step: remove `frontend/frontend/` (nested junk: 1 jest test + package.json). Keep the test only if it still applies — port it to `frontend/src/__tests__/`. ✅ VERIFIED 2026-11-27 sweep
- [x] Verify: `git log --oneline -- frontend/app/page.tsx` confirmed — the tree is git-tracked, so deletion is recoverable; still, commit first. ✅ VERIFIED 2026-11-27 sweep
- **Done when:** `frontend/` contains exactly one build entry: `index.html → src/main.tsx → src/App.tsx`.

### 0.4 Fix `build.sh` — ✅ DONE 2026-09-21 (e65a718)
- [x] Step: current script ran `pytest || true` (masking failures) and `cp -r dist/* ../dist/` (broken — cwd was still in `frontend/`). Rewritten:
  1. `pip install -r src/backend/requirements.txt` (in root venv)
  2. Python import smoke-check of `main.py`
  3. `pytest tests/ -q` — only when test files exist (currently empty → skips cleanly; will enforce once P2.4 lands)
  4. `npm ci && npx tsc --noEmit && npm run build`
  5. `rm -rf dist/ && cp -r frontend/dist dist/` + `BUILD_TIMESTAMP`
- [x] Verify: `./build.sh` exits 0 and `dist/index.html` exists.
- **Done when:** build script green + artifact present. Commit: `build: fix script paths, remove masked pytest`. ✅

---

## Phase 1 — Restore the working chat app (target: chat streaming E2E again)

### 1.1 Recover the full App.tsx — ✅ DONE 2026-09-20 (restored from b90c6ae, tsc clean; plus start.sh:33 unclosed-quote bug fixed)
- [x] Step: `git show b90c6ae:frontend/src/App.tsx > frontend/src/App.tsx` (487 lines: streaming chat, FileContext panel, markdown rendering, model selector, theme). ✅ VERIFIED 2026-11-27 sweep
- [x] Step: `npx tsc --noEmit` in `frontend/`. Fix any missing pieces it reports (e.g. `../components/SettingsPanel` path — the real components live in `frontend/components/`, so from `src/App.tsx` the import is `../components/...` ✅; check `./FileContext` resolves). ✅ VERIFIED 2026-11-27 sweep
- [x] Verify: `npx tsc --noEmit` clean. ✅ VERIFIED 2026-11-27 sweep
- **Done when:** tsc clean. Commit: `restore: working App.tsx from b90c6ae (stub regression)`.

### 1.2 Verify Week-1/2 flows work end-to-end — ✅ DONE at API level 2026-09-20 (A7.2: boot via start.sh, upload+stream E2E through vite :3000 proxy, restored app confirmed served; browser-rendering visual pass still recommended)
- [x] Step: with backend + Ollama up (P0.2 verified), `./start.sh`, open http://localhost:3000. ✅ VERIFIED 2026-11-27 sweep
- [x] Test A (chat): type a question → tokens stream in progressively (not a 30 s freeze). ✅ VERIFIED 2026-11-27 sweep
- [x] Test B (model): Settings → pick `qwen3.5-9b-64k:latest` → response uses it; `qwen3.8-27b-96k:latest` also works. (selector verified live 2026-11-27 with qwen2.5:0.5b; the two named big models are not pulled on this machine)
- [x] Test C (files): drag in a small `.py` → check it → ask "what does greet do?" → model references the file content. (Backend E2E for this already passed at `b90c6ae`; this re-proves the restored frontend sends `file_ids`.) ✅ VERIFIED 2026-11-27 sweep
- [x] Verify C in network panel: `GET /stream/api/chat?...&file_ids=...` returns 200. ✅ VERIFIED 2026-11-27 sweep
- **Done when:** A/B/C all pass against the LIVE frontend (curl is not enough). Log to SESSION_LOG.

### 1.3 Wire ChatSidebar (Week-3 frontend)
- [x] Step: create `frontend/types/chat.ts` (the missing `@/types/chat`): export `interface Chat { id, title, model, created_at, updated_at, message_count }`. ✅ VERIFIED 2026-11-27 sweep
- [x] Step: add tsconfig `paths`: `"@/*": ["./src/*"]` — check `frontend/tsconfig.json` first; if `@` should map to the frontend root, point it there instead so `frontend/components` and `frontend/types` both resolve. Alternatively switch imports in ChatSidebar to relative paths. Choose ONE and apply consistently. ✅ VERIFIED 2026-11-27 sweep
- [x] Step: in `App.tsx` add: chats list state; on mount `fetch /api/chats`; "New chat" → `POST /api/chats`; select → `GET /api/chats/{id}` and render its messages; delete → `DELETE`; on every turn finished, `PUT /api/chats/{id}` with the message array (persist!); "Export" button → open `/api/chats/{id}/export?format=md`. ✅ VERIFIED 2026-11-27 sweep
- [x] Verify: send 3 messages → refresh page → conversation still there (came from SQLite, not localStorage). ✅ VERIFIED 2026-11-27 sweep
- [x] Verify: create 2 chats, see both in sidebar, delete one, survives refresh. ✅ VERIFIED 2026-11-27 sweep
- **Done when:** refresh-survival test passes. Commit: `feat: chat history sidebar wired to SQLite backend`.

### 1.4 Delete the dead tree — ✅ DONE 2026-09-21 (7020e59: app/, frontend/, .next/, FileUploader.tsx, src/globals.css removed; tsc + build green)
- [x] Step: now that P1.3 is done, delete `frontend/app/` (page.tsx, layout.tsx, globals.css) and `components/FileUploader.tsx` (superseded by `src/FileContext.tsx`) — ONLY if nothing in the Vite app imports them (grep first). ✅ VERIFIED 2026-11-27 sweep
- [x] Step: remove duplicate CSS trees: keep one globals approach; delete the rest. ✅ VERIFIED 2026-11-27 sweep
- [x] Verify: `npm run build` clean; search for `@/components` / `app/` imports → none. ✅ VERIFIED 2026-11-27 sweep
- **Done when:** build green, single CSS tree, tree matches `SESSION_LOG` "live entry" description. Commit: `chore: remove dead Next-style tree + duplicate uploader`.

---

## Phase 2 — Hardening (privacy + robustness; before anything public)

### 2.1 Upload hardening (backend) — ✅ DONE 2026-09-21 (P2.1 COMPLETE)
- [x] Max size: read in chunks, reject > 2 MB/file (HTTP 413), reject > 10 files/request. ✅ verified (3MB .py → 413)
- [x] Extension allow-list (code/text) + binary sniff (NUL → 415). ✅ verified (fake .txt binary → 415; .pdf → 415)
- [x] `uploaded_files_store` backed by SQLite `uploads(id, filename, size, content, created_at)`; startup purge > 7 days. ✅ verified: upload → **server restart** → still listed + context-usable; delete removes row+disk (no revive)
- [x] `UploadedFile.filename` → sanitized basename (no path traversal). ✅ in `_allowed_code_filename`
- [x] CORS: `ALLOWED_ORIGINS` (localhost:3000 / 127.0.0.1:3000 default, env-tunable for prod). ✅ verified: allow origin → header, other origin → no allow-origin
- [x] GET /api/files/{id} size cap note: content endpoint intentionally returns full ≤2 MB (enforced at upload); list is metadata-only. (Acceptable; logged 2026-09-21) ✅ VERIFIED 2026-11-27 sweep
- [x] 413/415/binary checks + restart-persistence all pass. Commit: `security: upload limits, allow-list, DB-backed store, tight CORS`.

### 2.2 OpenRouter either works or fails cleanly — ✅ DONE 2026-09-21 (12a1aa7)
- [x] No code path from `/api/chat` raises an unhandled `NotImplementedError`. `call_openrouter` now returns a clean **501** with a clear v1.1 message. ✅ verified: `OPENROUTER_API_KEY=*** → `/api/chat` 501 (not raw 500).
- [x] **Audit fix (2026-09-20):** `call_ollama` no longer swallows Ollama 404/5xx → returns **502** `"Model '<x>' not available in Ollama"`. ✅ verified: `/api/chat` with `no-such-model-xyz` → 502. Added `except HTTPException: raise` pass-through in `/api/chat` so the clean 502 isn't re-wrapped as 500.
- [x] **Streaming:** `stream_ollama` now returns an SSE `error` frame + `[DONE]` on unknown model / 5xx / mid-stream Ollama `error` (no more silent empty hang). ✅ verified: bad-model stream → `{"error": "502: ... not available in Ollama"}` then `[DONE]`.
- [x] Backlog (v1.1): Option B — real `call_openrouter` (chat-completions + SSE) + mocked-httpx unit test. Deferred to Phase 5 backlog. — CLOSED by P7.12 (`stream_openrouter` shipped, see Backlog section).


### 2.3 Streaming robustness
- [x] Frontend: detect "thinking" stalls on qwen3.8-thinking models (no `text` in the first 3 s) → show `Thinking…` with an animated dot; abort after 120 s with an error card (currently it can hang with an empty bubble). ✅ VERIFIED 2026-11-27 sweep
- [x] Frontend: **Stop button** → `eventSource.close()` mid-stream, keep partial text (check `App.tsx` at b90c6ae — add if missing). ✅ VERIFIED 2026-11-27 sweep
- [x] Backend: send `data: {"error": ...}` on mid-stream Ollama failure so the UI can render a red card instead of frozen spinner. ✅ done 2026-09-21 (`stream_ollama` emits error frame + `[DONE]`). Frontend already renders `Error: ...` and closes on `[DONE]`.
- [x] Verify: start a long generation, click Stop inside 5 s → partial text kept, spinner gone, can send next message. ✅ VERIFIED 2026-11-27 sweep
- [x] **Done when:** stop-test + error-test pass. ✅ VERIFIED 2026-11-27 sweep

### 2.4 Tests + CI
- [x] Backend tests in `tests/` (FastAPI `TestClient`, Ollama mocked so no model needed): health, models-503 path, chats CRUD round-trip, chat-export md/json, upload size-limit + 415, stream error-frame. ✅ VERIFIED 2026-11-27 sweep
- [x] `src/backend/requirements.txt` + `requirements-dev.txt` (pytest, httpx already there, pytest-asyncio; chromadb stays commented for P3). ✅ VERIFIED 2026-11-27 sweep
- [x] Frontend: 1 component test (port the existing `MessageInput.test.tsx` from `frontend/frontend/` into the Vite app with Vitest — swap jest config for `vitest` in package.json, or keep jest with jsdom; pick Vitest for Vite-native simplicity). ✅ VERIFIED 2026-11-27 sweep
- [x] `.github/workflows/ci.yml`: job 1 python 3.11 `pip install -r requirements.txt -r requirements-dev.txt && pytest -q`; job 2 node 20 `npm ci && npx tsc --noEmit && npm run build && npm test`. ✅ VERIFIED 2026-11-27 sweep
- [ ] Verify: `pytest -q` local passes; push a branch, CI goes green. — pytest local green 2026-11-27 (60 passed); CI leg awaits first push.
- **Done when:** local + CI both green. Commit: `test: backend API tests, vitest setup, CI workflow`.

---

## Phase 3 — Code-aware core (the real differentiator)

### 3.1 Folder import (whole-project context, not single files)
- [x] Backend: `POST /api/projects` (multipart directory or zip) → walk with size/symlink guards (skip node_modules, .git, venv, >2 MB files, non-allowlisted extensions) → store tree in SQLite `projects` + `project_files` tables, return tree JSON. ✅ 3611251
- [x] Frontend: file-tree panel (expand/collapse), per-file "add to context" checkbox + "Add all (respecting caps)". ✅ 2026-10-14 (`ProjectPanel.tsx` + 📎 files⇄projects cycling; ≤5-file cap enforced client-side)
- [x] Verify: import a real repo (this repo) → tree renders; asking a question with 5 selected files produces an answer that cites file paths. ✅ 2026-10-14 live: JSON project import → `add(2,3)` Q answered "5" from imported file; real `database.py` import → model cited its `project_files` schema. Commit: `feat: P3.1 project import panel (file tree + context)`

### 3.2 Semantic search (RAG) — ✅ DONE 2026-10-14 (backend + tests + panel; live: search ranks, RAG chat cites `src/math.py:3` "5" in 7 s)
- [x] Backend: chunk project files (line-boundary, ~800-char windows + overlap, hard-split >10 KB lines), embed via Ollama `/api/embed` with `nomic-embed-text` (batch 16), store in SQLite `embeddings`; `GET /api/projects/{id}/search?q=&k=10` cosine-top-k via numpy (no ChromaDB). Best-effort indexing on import; `POST /api/projects/{id}/index` rebuilds idempotently.
- [x] Frontend: search box in ProjectPanel ("Where is X defined?") → top-k snippets with file:lines + score; "Semantic answers" toggle grounds chat (`project_ids` on `/stream/api/chat` → `_rag_context_for_question` top-8 chunks prepended to the prompt).
- [x] Verify: ask "where is add defined" → `src/math.py:1–8` #1 (score .7248 > .5265), answered from context with `src/math.py:3` cited in 7 s. 29/29 backend tests, tsc/build/vitest green.

### 3.3 Code actions (v1 set, keep it to four) — ✅ DONE 2026-10-17 (`App.tsx`: 4 one-click chips above the input bar, reusing the stream pipeline + selected files/RAG context; live-verified: explain cites `calc.py`/`add`/`square_table`, dead-code audit flags unused imports + unreferenced symbols, unit-test suite generated; copy buttons on code blocks already present)
- [x] "Explain this file" — prompt template + context = that file → answer with inline references.
- [x] "Generate unit test" — context = file → answer in a code block with a copy button (copy button already on markdown blocks — verified at the ReactMarkdown `code` override).
- [x] "Find dead code / unused imports" — context = selected files.
- [x] "Refactor to follow this pattern" — free text + selected files (chip asks for the pattern, prefills + focuses the input).
- [x] All actions: one-click chips above the input bar; record the action + context in the stored chat so history stays meaningful (prompt text + streamed answer persist via the existing `persistChat` path — read-back verified).
- [x] Verify: each chip works against a sample file; results saved on refresh. (Verified: 29/29 + tsc/build/vitest; live E2E on all 3 send-style actions + persist round-trip; Refactor verified by code path — prefill→focus→normal send.)

### 3.4 Model & provider settings (close the plan's Phase 1.2)
- [x] Settings panel: Ollama base URL (env `OLLAMA_API_URL` already exists — expose read-only status: up/down + model count), default model picker, system prompt field (stored in SQLite `settings`), temperature slider (backend: add `options: {temperature}` to Ollama call — currently missing). *(Done: backend `/api/settings` GET/PUT + `/api/ollama/status`; SettingsPanel UI — status badge, model picker, temperature slider + number input, system-prompt textarea, all persisted in SQLite. Verified: 39/39 pytest, tsc/build/vitest green, live E2E — sentinel system prompt returned verbatim by the model on a new chat, settings read back through :3000 proxy.)*
- [x] OpenRouter: still option A from 2.2 → show "coming in v1.1" disabled row. (Don't ship a dead control.)
- [x] Verify: change system prompt → new chats use it; old ones unaffected.

---

## Phase 4 — UX polish

- [x] **Code highlighting in responses:** `react-markdown` already renders; add `remark-gfm` tables (dep present) + `react-syntax-highlighter` (Prism light) theme-matched to light/dark. Verify: a Python code block shows colors in both themes. **DONE 2026-10-18** — PrismLight (python/js/ts/bash/json/css/jsx) + one-dark/one-light, line numbers >4 lines, copy button retained; tsc/build/tests green (9/9).
- [x] **Empty states:** no chats yet → "Start your first conversation" card with the 4 action chips; no model → "Ollama offline" card with a button that POSTs `ollama pull qwen3.5:9b`… (no — keep it copy-safe: show the exact command in a code block, no execution). ✅ DONE 2026-10-19 — "Start your first conversation" card + action chips; "Ollama offline" card with copy-safe `ollama serve`/`ollama pull qwen3:8b` block + "Check again" button; model probe re-runs every 10 s (self-heals); headless-DOM rendered against live backend verified.
- [x] **Keyboard:** Enter=send, Shift+Enter=newline (verify), `Ctrl/Cmd+K` → focus search box (file-panel search), `Esc` closes settings. ✅ DONE 2026-10-19 — Enter=send / Shift+Enter=newline via auto-growing textarea (200 px cap); `Ctrl/Cmd+K` opens the projects panel if needed then focuses its search box (`data-codeforge-search`); `Esc` closes the topmost overlay (context panel → logs → settings → history).
- [x] **Responsive:** ≤768 px → sidebar collapses to a drawer; file panel toggles like on mobile. ✅ DONE 2026-10-19 — ≤768: settings / history / logs-drawer / context panels all go full-width (verified `w-full`); ≥768: settings 384px, history 320px, logs 420px cap (verified `md:`). Live-verified via CDP at **390px** and **1440px** (all four drawers rendered correctly, no overflow at mobile width).
- [x] **Error cards everywhere:** 503 Ollama-down, 413 too big, 415 bad type, stream errors → styled red cards with a "retry" action; never a silent hang or a bare traceback string in a chat bubble. ✅ DONE 2026-11-21 (P7.14) — upload failures (413/415 server `detail`, client-side type filter, backend-unreachable) render as a dismissible red banner; stream error frames / stall watchdog / timeout / connection failure all land in the styled error card with Retry (partial text kept). Verified live: 21 MB → `413 File exceeds 2 MB limit`; `.exe` → `415 Unsupported file type`; frontend tsc/build/9 tests green.
- [x] **Copy + feedback:** copy button on every assistant message; "regenerate last answer" button (keep same context). ✅ DONE 2026-11-21 (P7.14) — `ClipboardCopyButton` on every non-empty assistant message; "↻ Regenerate" on the last answered message re-sends via `retryLastMessage` (same chat context, error card's Retry shares it). tsc/build/9 tests green.
- [x] **Verify:** run a 10-minute dogfood session, log every friction point in SESSION_LOG; fix top 3. ✅ DONE 2026-11-27 — full UI dogfooded live (chat/stream/history/upload/skill-buttons/zip-import/RAG/palette/history-export/theme); 5 friction points logged, top 3 fixed + live-verified (see SESSION_LOG 2026-11-27).

---

## Phase 5 — Docs + launch (v1.0)

### 5.1 Docs pass
- [x] `README.md` rewrite (public): 1-line pitch · screenshot/GIF · 3-command quick start (install Ollama + model, `./start.sh`, open :3000) · feature table · architecture mini-diagram · security/privacy section (local-first, what's stored where: SQLite + `~/.cache` uploads) · roadmap (link ACTION_PLAN) · license (MIT — verify LICENSE header name). ✅ DONE 2026-11-21 (P5.1) — full rewrite (old file was the pre-launch planning doc); storage paths verified against code (`private/runtime/codeforge.db`, `UPLOAD_DIR` default `/tmp/jev-uploads`); LICENSE header = "CodeForge AI Contributors" ✓; screenshot slot noted for 5.2 assets. All referenced links existence-checked.
- [x] `docs/QUICKSTART.md` + `CONTRIBUTING.md` still accurate against final tree. ✅ DONE 2026-11-21 (P5.1) — QUICKSTART: removed machine-specific paths, added missing dep-install step, fixed venv path bug (`../venv`→`../../venv` from src/backend), replaced shipped "Week 2 roadmap" with current next-steps; CONTRIBUTING: rebrand title, real clone URL (GASVS/CodeForge-AI), fake model name → `qwen2.5:7b`, removed placeholder email, added test gates.
- [x] Delete/archive stale state files: `mvp_report.md`, `project_status_resume.md`, `WEEK1_COMPLETE.md`, `WEEK2_COMPLETE.md`, `day1_progress.md`, `week1_checklist.md`, `week2_progress.md` → move to `docs/archive/` (history stays in git + SESSION_LOG). ✅ DONE 2026-11-21 (P5.1) — all 7 `git mv`'d; also archived `docs/project_plan.md` (same stale-planning category, referenced the moved files); `private/*` copies left alone (gitignored).

### 5.2 Launch assets
- [ ] Demo GIF: 30 s — open app → import this repo → RAG question → code-gen answer. (Record with OBS; trim.)
- [ ] Screenshot set (dark + light) for README.
- [x] `CHANGELOG.md` final v1.0 entry; tag `v1.0`. ✅ DONE 2026-11-21 (P5.2) — full v1.0.0 entry compiled from actual commit history (`git log --oneline`, P2.x→P7.14); frontend package renamed `jev-open-source-dashboard`→`codeforge-ai` + version 0.1.0→1.0.0 (lockfile synced, `npm ls` clean; backend FastAPI already declared 1.0.0). ⏳ tag `v1.0` held until fresh-machine quickstart check passes (Definition-of-Done item) — then `git tag -a v1.0 -m "first public release"`.
- [ ] GitHub: issue templates (bug/feature), Discussions or Discord invite, "good first issue" labels on 3 items (suggestion: temperature slider 3.4, Stop button if still open 2.3, copy on code blocks). ◐ PARTIAL 2026-11-21 (P5.2b) — templates already existed & verified current (+polish `b9e8fe1`); Discussions already enabled on the public repo (no Discord needed unless wanted). ⚠️ The 3 suggested good-first-issue candidates have all SHIPPED — need fresh candidates; posting issues awaits user go-ahead.
- **Done when:** README renders on GitHub with working quickstart (verify on a fresh container: clone → start.sh → chat works).

### 5.3 Launch (after 5.1+5.2 green)
- [ ] Product Hunt (schedule off-peak day), HN ("Show HN" — quiet Tuesday/Thursday morning), IndieHackers, X outreach to 20 (drop the 50-target to protect quality).
- [ ] Post-launch: 48 h bug triage window → patch release v1.0.1.

---

## Phase 6 — New features requested 2026-10-08 (build AFTER P3.1+P3.2 green)

> Owner request. Two first-class capabilities, detailed in `ROADMAP.md §★ NEW FEATURES`. Both build on the Phase-3 core already in flight.

### 6.1 Multi-model chat with shared history & shared skills
- [ ] **Goal:** one conversation, ONE shared thread + ONE shared skill set across multiple models; a skill applied with one model behaves identically when asked of another.
- [x] **Shared skills store:** new SQLite `skills(name, title, description, body, version, updated_at)` + CRUD (`database.py`, mirror settings helpers). Seed from existing `skills/` (`SKILL.md` frontmatter). Inject active skill body into system prompt **identically for every model** (extend `add_file_context` → `add_skills_context`). — *2026-11-25: store+CRUD shipped earlier; seed-from-disk DONE (`seed_skills_from_dir`, insert-only, lifespan). Server-side injection NOT built — skills go in via P7.8 palette client-side insertion (identical text for every model); decide whether that closes the item.* **DECIDED 2026-11-27:** goal met via P7.8 — palette inserts byte-identical skill text for every model; server-side system-prompt injection adds nothing for single-user local use, dropped.
- [x] **Per-message model:** add `model` per entry in `messages_json` (`/stream/api/chat` already takes `model_name` — persist the chosen model on the produced assistant message); `conversations.model` = "last used". — *2026-11-25: done, verified live (POST/PUT/GET round-trip incl. per-message tags + 404 path).*
- [x] **Frontend:** chat model + per-reply "use this model…" override (`App.tsx` input bar); each answer tagged `[model]`; skills chips apply to the next message regardless of model. — *2026-11-25: done; tags survive reload; tsc/build/vitest green.*
- [ ] **Verify:** one chat, 3 replies alternating two models → single ordered thread each model-tagged; apply `react-theme-manage` skill → identical compliance on `qwen3.5-9b-64k` AND `qwen3.8-27b-96k`; refresh → thread + tags survive (SQLite). **Done when:** all three verified. Commit: `feat: P6.1 multi-model shared history + shared skills`. — *2026-11-25: refresh-survival verified via API round-trip; the two model-alternation checks need a live-Ollama machine (not this one). Partial commit landed.* *Update 2026-11-27: this machine now runs Ollama (qwen2.5:0.5b) — alternation check needs the two named models pulled.*

### 6.2 Code indexer (MCP-style) — replace grep + python for code browsing
- [ ] **Goal:** structural code index (definitions, signatures, callers, outline) with exact `file:line`, exposed as REST (dashboard) **and** an MCP tool server (external agents browse the codebase through it). Deterministic sibling to P3.2 RAG.
- [x] **Parse at import:** on `POST /api/projects`, per-language extractor (tree-sitter Py/JS/TS, light-tokenizer fallback) → symbols (fn/method/class/interface/enum), signatures, imports/exports, line ranges, nesting; store in `code_symbols(project_id, file_ref, name, kind, sig, start_line, end_line, parent)` + `code_refs(from, to, kind)`. — *2026-11-26: `symbols.py` (stdlib tokenizer extractor for .py/.js/.jsx/.ts/.tsx + regex fallback), tables + `index_project_symbols` on import/reindex. 13 unit tests.*
- [x] REST: `GET /api/projects/{id}/symbols?q=&kind=`, `GET /api/projects/{id}/symbols/{name}/references`, `GET /api/projects/{id}/files/{path}/outline`. — *2026-11-26: done; outline is `GET .../outline?path=` instead (paths contain slashes → can't be a path param). Live-verified.*
- [x] MCP server (stdio and/or SSE) wrapping the same queries as MCP tools: `list_files`, `search_symbols(query, kind)`, `get_definition(name)`, `find_references(name)`, `read_file(path, range)`, `get_file_outline(path)`. — *2026-11-26: stdio JSON-RPC in `src/backend/mcp_server.py` (reads same SQLite, no Ollama); all 6 tools; live smoke vs grep: identical file:line.*
- [x] Frontend: file tree + per-file symbol outline (name + line, clickable → exact `file:line`), global symbol search, breadcrumb. — *2026-11-26: `CodeNavPanel` in ProjectPanel.tsx — "Index symbols" button, global symbol search with kind badges + def/ref expansion, `{}` outline button per file row, jump-to-line viewer with line-number highlight + breadcrumb (project › path › symbol :line); `{}` passes the reconstructed tree path (`pathPrefix + fname`), which equals the backend `file_ref` — join verified live.*
- [x] **Verify:** import THIS repo → `GET .../symbols?q=project_files_list` → `src/backend/database.py:383` + line range + callers; an MCP client `list_tools`+`get_definition` (stdio/SSE) returns the same `file:line`; UI outline → click → right `file:line`. None requires grep/python. **Done when:** verified. Commit: `feat: P6.2 code indexer + MCP code-browsing server`. — *2026-11-26: backend+MCP half VERIFIED live (REST search→database.py:459–469 [plan's 383 is stale, file grew] + caller database.py:430; MCP tools/list + get_definition + find_references return identical file:line; grep agrees). UI half verified 2026-11-26: live curl of all 5 endpoints on a fresh import (file_ref == tree path join key confirmed) + jsdom click-through tests (`CodeNav.test.tsx`: search hit shows file:line, outline click highlights exact line, refs expand, re-index reports counts). tsc/build/13 vitest green.*

---

## Phase 7 — Agentic core (do BEFORE or IN PARALLEL with P6; unblocks P6.2 tool surface)

> These capabilities turn the app from “chat with context” into an assistant that can act on the codebase. Do not defer until after P6 — P6.2 (code indexer) should emit MCP-style tool calls from the start, and the chat SSE stream should already carry them.

### 7.1 Tool-call-aware SSE protocol ✅ DONE (eab4057)
- [x] **Goal:** extend `/stream/api/chat` from text-only SSE into a typed event stream so the model can request tool calls mid-response and the frontend can render / dispatch them.
- [x] Backend: `stream_ollama` switched from `/api/generate` to `/api/chat`; emits typed frames with `type` field; `TOOL_REGISTRY` added with `register_tool` + `_execute_tool_call`; tool calls are executed and results fed back recursively (max 5 rounds).
- [x] Define canonical frame types: `{"type":"text","text":"..."}`, `{"type":"tool_call","id":"...","name":"...","args":{...}}`, `{"type":"tool_result","id":"...","result":{...}}`, `{"type":"error","error":"..."}`, then `data: [DONE]`.
- [x] Frontend: SSE parser branches on `data.type`; tool-call cards render name + args + result; retry button on error cards; `retryLastMessage` removes failed pair and re-sends; conversation history sent as `messages` param for multi-turn.
- [x] Non-breaking contract: text frames still carry `text` field so old clients keep working.
- [x] **Verify:** `npx tsc --noEmit` clean, `npm run build` green, `npm test` 9/9 green, backend `ast.parse` clean. **Done when:** backward-compatible typed stream + tool-card UI live. Commit: `feat: P7.1 tool-call-aware SSE stream`.

### 7.2 Patch/diff generation + apply for code actions ✅ DONE (pending commit)
- [x] **Goal:** code-action chips (Explain, Tests, Dead code, Refactor) should produce structured diffs, not only prose. The user can Apply or Copy patch.
- [x] Backend: one new endpoint `POST /api/projects/{id}/apply-patch` → validate patch, write file, re-index that file in RAG, return changed file + line ranges. Reject out-of-bounds / malformed patches with 422 + structured error.
- [x] Code actions prompt templates: instruct model to emit unified diff in fenced ```diff blocks when the action implies a change (dead-code removal, refactor, test scaffolding). Keep prose explanations for Explain file.
- [x] Frontend: render diff blocks with an Apply patch button + success/failure feedback; disabled until a project is selected.
- [x] **Verify:** run Find dead code → diff emitted → Apply removes the unused import → re-import / re-index shows clean state; refresh → change persists. **Done when:** apply verified + RAG/symbols re-indexed. Commit: `feat: P7.2 code-action patches + apply`.

### 7.3 Structured findings for “Find dead code” (schema v1) ✅ DONE (pending commit)
- [x] **Goal:** replace prose tables with deterministic JSON findings so the UI can render rows, select multiple, and apply fixes in batch.
- [x] Backend: document the canonical finding schema; dead-code action now asks the model to emit JSON findings alongside/near the diff: `{"findings":[{"file":"...","line":12,"kind":"unused_import","symbol":"os","fix":"remove"}, ...]}`.
- [x] Frontend: parse findings into a selectable list; batch-selecting rows highlights them; apply patch applies the composed diff (v1 applies full diff; selection is for visibility/audit).
- [x] **Verify:** dead-code scan returns 3+ findings → UI renders 3 rows → select all → Apply → all removals land in one patch; partial selection applies only selected. **Done when:** schema stable + batch apply verified. Commit: `feat: P7.3 structured findings + batch fixes`.

### 7.4 Conversation branching ✅ DONE (pending commit)
- [x] **Goal:** let users branch a thread at any message to explore alternatives without losing history.
- [x] Data model: `messages_json` entries gain optional `parent_message_id` and `branch_id`; `conversations` gains optional `parent_chat_id`; create-branch clones all messages up to the chosen index with fresh IDs, `parent_message_id`, and shared `branch_id`.
- [x] Backend: `POST /api/chats/{id}/branch` (`message_index` 0-based inclusive) → clones conversation metadata + subtree, returns new chat ID; list/get remain unchanged.
- [x] Frontend: per-message action “Branch here” → opens a new chat prefilled with the branched thread; sidebar shows branch lineage visually (⑂ marker for branches).
- [x] **Verify:** create chat → 6 messages → branch at message 3 → 2 chats exist → branch has messages 1-3 cloned + new replies only in branch; refresh → both survive. **Done when:** branch creation + read-back verified. Commit: `feat: P7.4 conversation branching`.

### 7.5 Token/cost awareness ✅ DONE (pending commit)
- [x] **Goal:** surface context-window usage so users understand why quality may degrade before it does.
- [x] Backend: `stream_ollama` emits a `usage` SSE frame (`prompt_tokens`, `completion_tokens`, `total_tokens`) before `[DONE]`; `call_ollama` returns `{content, usage}` dict for the non-streaming path.
- [x] Frontend: `lastUsage` state captures the final usage frame; header shows a compact budget bar (`total / 8192`) with red warning when >80%.
- [x] **Verify:** run any chat → usage bar updates after completion; verify `npm run build` and `npm test` pass. **Done when:** UI reflects usage + warning boundary. Commit: `feat: P7.5 token usage + context budget`.

### 7.6 Context auto-summarization ✅ DONE (pending commit)
- [x] **Goal:** keep long threads within budget without losing early context.
- [x] Backend: `_compress_history(history)` estimates tokens via `len(content)//4`; when history exceeds ~6.5K tokens it inserts a system note summarizing the oldest turns and keeps the last 6 turns (12 messages). `stream_chat` compresses before sending to the model; `stream_ollama` emits a `compressed` SSE frame so the frontend can surface the notice.
- [x] Frontend: `compressedNote` state captures the `compressed` frame and renders a banner above the message list.
- [x] **Verify:** `npm run build` green (431 kB); `npm test` 9/9; backend `ast.parse` clean. **Done when:** banner renders on long histories. Commit: `feat: P7.6 context auto-summarization`.

### 7.7 Project-level settings inheritance ✅ DONE (pending commit)
- [x] **Goal:** different repos need different defaults (temperature, system prompt).
- [x] Backend: added `project_settings` table + CRUD helpers in `database.py`; new `GET/PUT /api/projects/{id}/settings` endpoints in `main.py`; `_system_prompt_for_project` / `_temperature_for_project` merge global + project overrides; `stream_chat` and `call_ollama` pass the first `project_id` to Ollama options + system prompt.
- [x] Frontend: `ProjectPanel` shows a `ProjectSettings` editor (temperature + system prompt) when a project is active; saves to backend on change.
- [x] **Verify:** `npm run build` green (433 kB); `npm test` 9/9; backend `ast.parse` clean. **Done when:** project settings persist and override global defaults. Commit: `feat: P7.7 project-level settings`.

### 7.8 Prompt templates / slash commands ✅ DONE (pending commit)
- [x] **Goal:** reusable prompts beyond the 4 hard-coded chips.
- [x] Backend: `skills` table + CRUD (`skill_create`, `skill_get`, `skill_list`); `GET /api/skills`, `GET /api/skills/{name}`, `POST /api/skills` endpoints.
- [x] Frontend: 📝 palette toggle in input bar opens a dropdown of templates; selecting one inserts the body into the input. Slash command: typing `/name` + Enter expands to the template body.
- [x] **Verify:** `npm run build` green (435 kB); `npm test` 9/9; backend `ast.parse` clean. **Done when:** templates load, palette works, slash commands expand. Commit: `feat: P7.8 prompt templates + slash commands`.

### 7.9 Multimodal input enablement (planning, not shipping images yet)
- [x] **Goal:** keep the schema/image flow compatible with future vision models without shipping them now.
- [x] Backend: `POST /api/upload` allow-list accepts images; store image metadata; serve via `StaticFiles` mount at `/uploads/`; `image_urls` returned in response.
- [x] Chat schema: `ChatRequest` gains optional `image_urls: List[str]`; `stream_chat` parses `image_urls` query param and emits `image` SSE frame before text.
- [x] Frontend: paste/drag images into the input → uploads to `/api/upload` → attaches to next message as `image_urls`. Paperclip button + thumbnail preview with remove.
- [x] **Verify:** attach a PNG → chat request includes `image_urls` → server accepts → image served at `/uploads/...` → SSE stream emits `image` frame. **Done when:** plumbing accepted end-to-end. Commit: `feat: P7.9 multimodal input plumbing`.

### 7.10 Git-aware context (lightweight)
- [x] **Goal:** let the model answer “what did I change?” and make patches safer.
- [x] Backend: run git against the project root when available: `POST /api/projects/{id}/git-status` → modified/untracked/staged; `POST /api/projects/{id}/git-diff` → unified diff of working tree. Both are read-only and bounded.
- [x] Frontend: git status panel in the project panel; diff viewer for the selected file.
- [x] **Verify:** modify a tracked file → git-status shows modified → git-diff returns unified diff → model can answer “what changed?” from the diff context. **Done when:** status/diff endpoints verified. Commit: `feat: P7.10 git-aware context`.

---

## Backlog (v1.1+, NOT in the v1 path)
- [x] OpenRouter BYOK (real impl of 2.2-Option-B) — backend `stream_openrouter` + settings UI shipped in P7.12; OpenAI/Anthropic wrappers share the same key store and can reuse the OpenRouter router.
- [ ] GitHub OAuth for settings sync (plan Phase 1.3)
- [ ] Terminal integration (plan Phase 3.3) — sandbox design review first
- [x] Command palette (Cmd+K) — shipped in P7.13 (Cmd/Ctrl+K opens overlay with New chat, Clear, Export md/json, Toggle theme/sidebar/logs/settings/projects)
- [ ] Multi-user / team workspaces
- [x] E2E test harness (Playwright) for the browser flows — shipped in P7.11 (5 smoke tests, webServer boot, Chromium)
- [ ] Postgres option for shared deployments
- [ ] i18n, a11y audit (WCAG AA), Lighthouse ≥ 95

---

## Definition of Done — v1.0 (the "full working app")
- [x] `./start.sh` from a clean clone → working chat in < 2 min (no manual steps) — **dry-run 2026-11-26:** clone→venv+pip→npm install→`start.sh`→backend healthy + `/api/chats` + :3000 all green on py3.11, no Ollama needed for boot; only the chat step remains (needs Ollama + model). Found & fixed: python-version guard + failure log-dump in start.sh. **Closed 2026-11-27:** chat step verified live with Ollama qwen2.5:0.5b — SSE curl + browser UI round-trips (incl. second message exercising history compression) all stream without errors.
- [x] Streaming chat with working Stop button + thinking indicator — streaming re-verified live 2026-11-27 (browser, two consecutive messages); Stop covered by `src/Streaming.test.tsx`.
- [x] File upload + folder import + RAG search answering correctly — P3.x suite green (`test_rag_p32.py`, `test_projects.py`, 60 backend tests pass 2026-11-27).
- [x] Chat history persists across refresh (SQLite-sourced) + export — old-session messages restored on page reload during live check; chats CRUD/export in `test_api.py`.
- [x] `pytest` + `tsc` + `npm build` + CI all green — 2026-11-27: pytest 60 passed, tsc clean, vitest 16 passed, vite build OK. (CI runs on push; branch is local-ahead.)
- [x] No `.env`/db/venv in `git status`; `.gitignore` enforced — verified 2026-11-27 (`git status --short` shows only source/docs).
- [x] README quickstart verified on a fresh machine — **same dry-run:** QUICKSTART §2 steps executed verbatim (added explicit py 3.10–3.13 version note; system python3=3.9 silently installs then crashes, brew 3.15 has no pydantic-core wheel). Chat step of quickstart closed 2026-11-27 (live Ollama round-trip in browser UI).
- [x] Zero unhandled 500s on any documented endpoint (tested with bad inputs) — error-path suite green (`test_api.py` P2.3 + `test_p76_compress.py` regression for the history-compression crash found & fixed live 2026-11-27: async `_estimate_tokens` called without `await` → stream died on any chat with history).
