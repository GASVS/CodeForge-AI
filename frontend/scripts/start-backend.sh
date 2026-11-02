#!/bin/bash
# Wrapper to start the backend with the Python that has uvicorn + app deps.
# Playwright webServer will call this script directly.
cd "$(dirname "$0")/../.."
PYTHON_BIN="/Users/andrejgorskolepov/.hermes/tools/python-current/bin/python3"
# Add Hermes site-packages so uvicorn + fastapi deps are importable
SITE_PACKAGES=$(find /Users/andrejgorskolepov/.hermes/installs -path "*/site-packages" -type d 2>/dev/null | head -1)
if [ -n "$SITE_PACKAGES" ]; then
    export PYTHONPATH="$SITE_PACKAGES${PYTHONPATH:+:$PYTHONPATH}"
fi
exec "$PYTHON_BIN" -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8001
