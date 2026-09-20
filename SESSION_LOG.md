# 📋 SESSION LOG — CodeForge AI (Jev Open Source Dashboard)

> **RULE: After EVERY completed action, append/update its status below before moving on.**
> If the session crashes, the next session reads this file FIRST and resumes from here.

**Project goal (unchanged)**: Free, privacy-first, open-source AI coding assistant (local Ollama models, code-aware chat). Weeks 1–2 shipped (chat + streaming + file upload API). **Current objective: repair broken build, wire file context end-to-end, then Week 3 (persistent chat history).**

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
| 14 | Week 3: SQLite conversation store (save/load/delete/export) | ⬜ TODO | backend `database.py` + endpoints |
| 15 | Week 3: history sidebar in App.tsx (load past chats, new chat, delete) | ⬜ TODO | |
| 16 | Week 3: export chat to Markdown/JSON | ⬜ TODO | |
| 17 | Update README + docs/WEEK3, commit | ⬜ TODO | |

---

## 🔁 ACTION LOG (newest last)

### Session 2026-09-20 (this session)
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
