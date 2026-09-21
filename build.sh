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

# Smoke-check that the API module imports cleanly (catches import regressions
# without needing a running server).
python -c "import sys; sys.path.insert(0, 'src/backend'); import main; print('✅ backend imports OK')"

# Run the test suite if any backend tests exist; once the P2.4 tests land,
# this gate enforces that they pass (an empty suite must not fail the build).
TEST_FILE=$(find tests -maxdepth 1 -name 'test_*.py' 2>/dev/null | head -n1)
if [ -n "$TEST_FILE" ]; then
  echo "🧪 Running backend tests…"
  python -m pytest tests/ -q
else
  echo "⚠️  No backend tests yet (tests/ is empty) — skipping (expected pre-P2.4)."
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
