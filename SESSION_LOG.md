# 📋 SESSION LOG — CodeForge AI (Jev Open Source Dashboard)

> **RULE: After EVERY completed action, append/update its status below before moving on.**
> If the session crashes, the next session reads this file FIRST and resumes from here.

**Project goal (unchanged)**: Free, privacy-first, open-source AI coding assistant (local Ollama models, code-aware chat). **Status 2026-09-21: Weeks 1–3 shipped (chat + streaming + file context + SQLite persistence + export), repo cleaned of dead tree, backend hardened (P2.1+P2.2).** **Current objective: P2.3 (streaming Stop button + thinking indicator) → P2.4 (tests + CI) → Phase 3 code-aware core (folder import / RAG / code actions) → Phase 4 polish → Phase 5 launch.**

---

## 🗺️ DETAILED PLAN (in order)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Fix `interface Message {` missing in App.tsx | ✅ DONE | Was fatal syntax error (TS1128) |
| 2 | Fix stale imports in App.tsx (`./components/*` → `../components/*`) | ✅ DONE | Removed unused MessageList/MessageInput imports too |
| 3 | Fix `process.env.NEXT_PUBLIC_API_URL` in App.tsx (Vite, not Next) | ✅ DONE | → `import.meta.env.VITE_API_URL \|\| localhost:8001`; model fallback picks first installed model (qwen3.8-27b-96k) |
| 4 | Fix `FileList \| null` typing in App.tsx file input | ✅ DONE | (block later removed — see 9) |
| 5 | Fix duplicate `style` prop in MessageInput.tsx (line 46/48) | ✅ DONE | Merged into one style object |
| 6 | Fix `process.env` in FileContext.tsx:29 | ✅ DONE | → import.meta fallback |
| 7 | Remove unused imports in App.tsx | ✅ DONE | Done as part of task 2 (kept SettingsPanel, FileContext, ReactMarkdown, remarkGfm) |
| 8 | Verify `npx tsc --noEmit` passes clean | ✅ DONE | "TSC OK" |
| 9 | Wire FileContext into App.tsx: uploadedFiles + selectedFiles state | ✅ CODE DONE | `showFilePanel` toggle; 📎 button in input bar; removed dead inline file input; UploadedFile.size → number. NOT YET COMPILE-VERIFIED |
| 10 | Backend: accept `file_ids` on `/stream/api/chat`, inject context | ✅ DONE | Verified via openapi.json (now lists file_ids). Also fixed `add_file_context` async→sync mismatch |
| 11 | E2E test: upload file via curl → ask about it via stream w/ file_ids | ✅ DONE | MODEL ANSWER: traced greet('x') → 'Hello X' from uploaded e2e_test.py. Context-awareness PROVEN |
| 12 | `npm run build` passes clean | ✅ DONE | 286 modules, 319 kB JS bundle, 1.13s |
| 13 | Commit: fixes + file-context wiring | ✅ DONE | b90c6ae |
| 14 | Week 3: SQLite conversation store (save/load/delete/export) | ✅ DONE | backend `database.py` + endpoints (A6 verified) |
| 15 | Week 3: history sidebar in App.tsx (load past chats, new chat, delete) | ✅ DONE | 88d2f75 + 625d1d6 (ChatSidebar tracked) |
| 16 | Week 3: export chat to Markdown/JSON | ✅ DONE | `/api/chats/{id}/export?format=md|json` (A6 verified) |
| 17 | Update README + docs/WEEK3, commit | 🟡 PARTIAL | README rewrite uncommitted; see ACTION_PLAN Phase 5 |
| 18 | P1.4: delete dead Next-style tree + dup uploader | ✅ DONE | 7020e59 |
| 19 | P2.1: upload limits / allow-list / tight CORS | ✅ DONE | 12a1aa7 (verified live: 413, 415, CORS) |
| 20 | P2.2: clean 502 on bad model + 501 OpenRouter | ✅ DONE | 12a1aa7 (verified live: 502 + 501) |
| 21 | P2.1: uploads persist across restart (SQLite) | ✅ DONE | 0c93d2d (upload→restart→list verified) |
| 22 | P0.4: fix build.sh (masked pytest, broken cp) | ✅ DONE | e65a718 (green, dist/index.html) |
| 23 | Logs tab: in-app live runtime logs (backend `/api/logs` + `LogsPanel` + start.sh capture) | ✅ DONE | 8ac4b3a (verified live: /api/logs merges vite tail + in-process buffer; tsc/build green) |

---

## 🔁 ACTION LOG (newest last)

### Session 2026-09-20 (this session) — DOC REALIGNMENT (code untouched)
- [✅] **A1** Verified reality vs docs (import test found blocking bug; git archaeology found App.tsx regression)
- [✅] **A2** Rewrote `docs/project_plan.md` — now reflects actual state (Vite not Next.js; Week-3 backend DONE incl. SQLite chats + export; regression of `src/App.tsx` documented: live entry is 66-line stub, full working version at `b90c6ae:frontend/src/App.tsx`; no-.gitignore risk; ChatSidebar broken `@/types/chat` import; dead `frontend/frontend/` + `frontend/app/` trees). 11,430 B on disk, verified.
- [✅] **A3** Wrote `docs/ACTION_PLAN.md` — full step-by-step plan P0–P5 (repo safety → restore chat app → hardening → code-aware core/RAG → polish → launch), each task with Steps / Verify / Done-when, plus v1.0 Definition of Done. 17,069 B on disk, verified.
- [✅] **A4** P0.1 done — `.gitignore` created (private/, *env*, *.db*, venvs, node_modules, dist, caches). Sensitive artifacts MOVED to `private/runtime/`: `frontend/.env.local`, `codeforge.db{,-shm,-wal}` (dev server on :8001 killed first). `database.py` now points `DB_PATH` → `private/runtime/codeforge.db` (auto-creates dir); verified: DB opens at new path, table intact (0 rows — was empty anyway). `git status`: ZERO sensitive untracked files; `git ls-files`: zero tracked sensitive paths. LEFT IN PLACE (gitignored, moving breaks absolute paths inside): 3× venv/, node_modules/, dist/, __pycache__.
- [✅] **A5** P0.2 done — `main.py`: `from . import database` → `import database`. Import test now clean, server boots via `uvicorn main:app`. **BUT NOT YET E2E-VERIFIED against the live frontend** (frontend is the stub — see A6).
- [✅] **A6** FULL BACKEND FUNCTIONALITY AUDIT (server booted, every endpoint exercised, then shut down):
  - ✅ `/health` → healthy; `/api/models` → 10 models listed
  - ✅ Chat CRUD: create→list→rename+append (PUT)→get→export MD (`# title` + You/Assistant sections, correct)→export JSON→delete→final count 0→404 on missing. **Persistence works; data landed in `private/runtime/codeforge.db` (new path confirmed working).**
  - ✅ Multi-file upload (2 files)→list→fetch content→delete both→list empty→404 on missing id
  - ✅ **Code-aware streaming E2E**: uploaded `greet` function, asked "what does greet return for X?" with `file_ids` → model replied: *It returns the string "Hello " concatenated with X.* (RAG-via-concat path genuinely works)
  - ✅ Non-streaming `POST /api/chat` → `{"type":"text","content":"PONG"}`
  - ✅ CORS preflight ok for origin :3000 (note: allow_origins still `*` — P2.1)
  - ✅ SSE frame hygiene: frames `data: {"text":...}`, ends `data: [DONE]`
  - 🐛 BUG NEW: bad `model_name` (no-such-model) → **200 + "No response from model"** (misleading; should be 502/400 "model not found" — Ollama returns 404, we swallow it in call_ollama's `.get("response","No response...")`)
  - 🐛 BUG CONFIRMED (known): `call_openrouter` still `NotImplementedError` → 500 when `OPENROUTER_API_KEY` set
  - 🐛 LEAK FOUND: `/tmp/jev-uploads/` accumulates stale files across sessions (3 old test files found) — no cleanup
  - ⚠️ Frontend live entry STILL the 66-line stub (tsc clean, `npm run build` green: 31 modules, 145 kB JS) — so NONE of the verified backend features are reachable in the running UI. Restore App.tsx (P1.1) is the critical path.
- [📌] ENV CHECK (2026-09-20): Ollama UP. Models: gpt-oss-20b (×3), qwen3.8-27b-96k, qwen3.8:27b, qwen3.5-9b/27b (64k/96k variants). Default model in code (`qwen3.5-9b-64k`) EXISTS ✅ — stale default risk lower than suspected.
- [✅] **A7.1 DONE — live stack E2E VERIFIED.** Restored App.tsx (487 L) → tsc clean → **found+fixed 2 more bugs while trying to boot**: (a) `start.sh:33` had an **unclosed quote** on the models-line `|| echo "..."` fallback → bash parsed the rest of the script as a string, **nothing after line 33 ever executed** (this is why start.sh had been silently broken beyond the import bug); fixed, `bash -n` OK. (b) (import bug was already fixed in A5). Boot now works: backend :8001 + vite :3000 both up via start.sh.
- [✅] **A7.2 DONE — full-stack E2E through the FRONTEND (vite :3000 proxy → :8001)**: `GET :3000/src/App.tsx` serves the RESTORED app (markers: EventSource=1, stream/api/chat=1, file_ids=1, api/models=1); proxy upload via `:3000/api/upload` → 200 w/ file id; streaming chat via `:3000/stream/api/chat` with `file_ids` → 200 (answered from context; empty-text one round was the qwen think-gap, frames end `[DONE]`); CORS ok. **The verified backend features are now reachable in the running UI.** Stack shut down + temp files cleaned after test.
- [✅] **A7 NEXT → DONE (2026-09-21 session)** Critical path to "full working app":
  1. ~~**P1.1** restore App.tsx + boot + E2E~~ ✅ DONE (A7.1 + A7.2)
  2. ~~**P1.3** Create `frontend/types/chat.ts` + wire ChatSidebar~~ ✅ CODE+BUILD (88d2f75) — **P0.1 commit gap CLOSED (625d1d6)**: 88d2f75 imported `../components/ChatSidebar` + `@/types/chat` but BOTH were untracked → fresh clone failed `npx tsc`. Now tracked along with `.gitignore` + `docs/ACTION_PLAN.md`; tsc clean, build green (287 mods).
  3. ~~**P2.2** Bad-model fix~~ ✅ DONE (12a1aa7): `call_ollama` 400/404/5xx→502 "Model not available"; `stream_ollama` now emits SSE `error`+`[DONE]` on bad model (no hang); `call_openrouter` → clean 501. Verified live: 502 (bad model, both endpoints), 501 (openrouter), happy-path stream OK.
  4. ~~**P2.1** CORS tighten + upload hardening~~ ✅ DONE (12a1aa7): `allow_origins` from `ALLOWED_ORIGINS` (localhost:3000/127.0.0.1:3000), env-tunable; upload ≤10 files (413) + ≤2 MB (413, chunked) + ext allow-list (415) + binary sniff (415) + basename sanitize; startup purge >7d. Verified live: 413 (3MB), 415 (bin+pdf), CORS allow-localhost/block-evil.
  5. ~~**P1.4** Delete dead tree~~ ✅ DONE (7020e59): removed `frontend/app/` (Next page/layout/globals), `frontend/frontend/` (broken jest tree), `frontend/.next/`, `components/FileUploader.tsx` (dup of FileContext), unused `src/globals.css`. Confirmed zero live references (grep: only `app/page.tsx` self-imports; main.tsx is the sole live entry). tsc clean, build green.
- [📌] **REMAINING (v1.0 path, in order)**: P2.3 streaming Stop button + thinking indicator (App.tsx has a 120 s timeout + spinner but no Stop/abort + no thinking dot yet); P2.4 tests+CI (backend `pytest` + vitest + `.github/workflows/ci.yml`); P3 code-aware core (folder import / RAG / 4 code actions); P3.4 model+temp settings; then Phase 4 polish + Phase 5 docs/launch.
- [📌] RULE re-affirmed: log ONE action at a time the moment it finishes (crashes lose unlogged work).
### Session 2026-09-21 (this session) — LOGS TAB (in-app live runtime logs)
- [✅] **L1** Backend: in-process logging ring buffer (1000 lines) + rotating `private/runtime/app.log` (1 MB × 2) wired to root logger in `main.py`; `GET /api/logs` endpoint returns merged lines (bounded 64 KB tails of `api_server.log`/`vite_dev.log` from `private/runtime/` + ring buffer). Removed 3 duplicate unused imports while editing.
- [✅] **L2** `start.sh`: uvicorn + `npm run dev` output now tee'd to `private/runtime/{api_server.log,vite_dev.log}` (line-buffered via `stdbuf -oL` when available) → vite/npm logs land in the files instead of being lost to the terminal. `bash -n` clean.
- [✅] **L3** Frontend: new `frontend/components/LogsPanel.tsx` (dark log pane, auto-refresh every 2 s, auto-scroll, error state if backend down) + header `>_` terminal button in `App.tsx` toggles it (emerald highlight when open).
- [✅] **L4** Verified: `npx tsc --noEmit` clean, `npm run build` green (326 kB bundle). Live E2E: booted uvicorn on :8002 → `/health` 200 → `/api/logs` returned vite tail lines + in-process httpx log lines → killed server, removed temp test artifacts.
- [📌] **NEXT (unchanged order):** P2.3 streaming Stop button + thinking indicator → P2.4 tests + CI → Phase 3 (folder import / RAG / code actions).
- [📌] ENV: Ollama models include `qwen3.5:9b` (fast, good for E2E — reply "PONG" in ~1s) and `qwen3.8-27b-96k` (thinking model, long empty-gap — use `qwen3.5:9b` for quick tests). Bad-model tests work with `no-such-model-xyz`.

### Prior session tasks (from old plan table, context only)
- [✅] **1** Restored missing `interface Message {` declaration — `frontend/src/App.tsx:15`
- [✅] **2** Pointed component imports at `frontend/components/` (real location)
- [✅] **3** API_URL now Vite-correct (`import.meta.env?.VITE_API_URL || http://localhost:8001`)
- [✅] **4** Fixed `Array.from(e.target.files)` null narrowing; input value reset after select
- [🔍] Inspected all components: `MessageInput.tsx` (dup style prop), `FileContext.tsx` (process.env; full-working upload UI, currently **not rendered anywhere**), `MessageList.tsx` + `SettingsPanel.tsx` (OK), `FileUploader.tsx` (deprecated duplicate of FileContext — candidate for deletion later, NOT YET DELETED)
- [🔍] Verified live env: backend healthy on :8001, Ollama up, installed model **qwen3.8-27b-96k:latest** (app default text says qwen3.5 — model list from API wins, acceptable)
- [📌] NEXT: task **5** (MessageInput dup style) → 6 → 7 → 8 (tsc) → 9/10 (wiring)

### Prior sessions (committed)
- Week 1: MVP chat UI + Ollama streaming + theme toggle (commit cb853a6, f300430, 4199a02)
- Week 2: file upload API (`/api/upload`, `/api/files`, `/api/files/{id}`) + FileContext.tsx (commit 0a63696)
- Docs: WEEK1_COMPLETE, WEEK2_COMPLETE, README rewrite uncommitted (staged as "modified: README.md" — content rebrand to CodeForge AI, **review + commit when convenient**)

---

## 💥 CRASH RECOVERY PROCEDURE
1. `git status && git diff --stat` — see uncommitted work
2. Read **this file**; find the first ⬜ TODO in the plan table
3. `npx tsc --noEmit` in `frontend/` to check for compile breakage
4. Continue from that task; update the log after each action

## ⚠️ PITFALLS LEARNED (read before restarting services!)
- **Stale server masks your fixes**: a uvicorn from a previous session held :8001 and silently ignored new code — my file_ids test failed because the OLD binary answered. After ANY backend edit: `kill $(lsof -ti:8001) -9`, wait, restart, then verify with `curl openapi.json` that the NEW signature shows up before testing.
- **venv path**: from `src/backend/` it is `../../venv` (project root) — use the absolute path `/home/andrej/Desktop/App/jev-opensource-dashboard/venv/bin/python`.
- **Qwen 3.8 "thinking" models**: Ollama streams reasoning into the `thinking` JSON field with empty `response` for 30–60s before the answer starts. A naive SSE reader that stops early (or a tight timeout) gets an all-empty stream. Frontend must wait / have a long timeout. (Consider showing a "thinking…" indicator.)
- Frontend is **Vite/React**, not Next.js: no `process.env.NEXT_PUBLIC_*`; use `import.meta.env`. The old `frontend/app/` (Next pages) tree is DEAD CODE — the live entry is `src/main.tsx → src/App.tsx`.
