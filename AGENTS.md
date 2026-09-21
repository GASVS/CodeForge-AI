# AGENTS.md — CodeForge AI (Jev Open Source Dashboard)

## The one non-negotiable rule: record as you go
Sessions crash; unrecorded work IS lost work. Therefore, **per task, in this order**:

1. **Implement** the task (from `docs/ACTION_PLAN.md`, top-to-bottom).
2. **Verify** it is actually working:
   - Backend: `venv/bin/python -m pytest src/backend/tests -q` (conftest isolates the DB; no Ollama needed)
   - Frontend: `cd frontend && npx tsc --noEmit && npm run build && npm test`
   - Live: boot the server, `curl` the real endpoint including the error path, then kill it
3. **Log it** in `SESSION_LOG.md` IMMEDIATELY — plan-table row (status + commit hash + one verification line) and one action-log entry.
4. **Commit it** — `git add -A && git commit -m "<P#>: <what>"`. One task = one commit; never stack two tasks uncommitted.
5. Only then start the next task. On session start, read `SESSION_LOG.md` FIRST and resume at the first unchecked task.

## Map of the repo
- **Plan** (what to do, in order, with Verify + Done-when per task): `docs/ACTION_PLAN.md`
- **Log** (what was done, verified how, with commit hashes): `SESSION_LOG.md`
- Backend: `src/backend/` (FastAPI + SQLite in `private/runtime/`) — tests in `src/backend/tests/`
- Frontend: `frontend/` (Vite + React; entry is `src/main.tsx → src/App.tsx`; components in `components/`)
- Runtime state (DB, logs, uploads): `private/runtime/` — gitignored, NEVER commit

## Ground rules
- Match existing code style; no drive-by refactors or reformatting.
- Never commit secrets, `.env`, `*.db`, venvs, `node_modules/`, `dist/` (`.gitignore` covers it — keep it so).
- Kill stale servers on `:8001` before re-running backend code (`kill $(lsof -ti:8001) -9`) — a stale uvicorn silently answers with old code.
- Commit messages: lowercase imperative, task ID where applicable (e.g. `feat: P3.1 project import + tree panel`).
- If a task cannot be finished (missing model, blocked command, crash): log EXACTLY where you stopped in `SESSION_LOG.md`, commit what is done, and note the resume step.
