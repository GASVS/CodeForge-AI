#!/usr/bin/env bash
# build.sh – Build CodeForge AI: install backend deps, run tests (if any),
# type-check + build the frontend (Vite), and stage it under dist/.
#
set -euo pipefail

cd "$(dirname "$0")"

# --- Backend --------------------------------------------------------------
echo "🔧 Backend: installing dependencies…"
source ./venv/bin/activate
pip install -q -r src/backend/requirements.txt
pip install -q -r src/backend/requirements-dev.txt

# Smoke-check that the API module imports cleanly (catches import regressions
# without needing a running server).
python -c "import sys; sys.path.insert(0, 'src/backend'); import main; print('✅ backend imports OK')"

# Run the backend test suite if tests exist (src/backend/tests/). Subshell so
# the cwd is unchanged for the frontend steps that follow.
TEST_FILE=$(find src/backend/tests -maxdepth 1 -name 'test_*.py' 2>/dev/null | head -n1)
if [ -n "$TEST_FILE" ]; then
  echo "🧪 Running backend tests…"
  (cd src/backend && ../../venv/bin/python -m pytest tests/ -q)
else
  echo "⚠️  No backend tests yet — skipping."
fi

deactivate

# --- Frontend -------------------------------------------------------------
echo "🎨 Frontend: type-checking + building…"
cd frontend
npm ci --no-audit --no-fund
npx tsc --noEmit
npm run build

# --- Stage distribution ----------------------------------------------------
cd ..
rm -rf dist
cp -r frontend/dist dist
echo "Built $(date -R)" > dist/BUILD_TIMESTAMP

echo "✅ Build finished — frontend staged under dist/"
