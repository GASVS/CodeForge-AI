#!/usr/bin/env bash
# build.sh – Builds the frontend and backend of Jev Open Source Dashboard

set -euo pipefail

# Build the backend (FastAPI)
echo "🔧 Building backend…"
source ./venv/bin/activate
pip install -r src/backend/requirements.txt
pytest --maxfail=1 || true

# Build the frontend (Vite)
cd frontend
npm install
npm run build

# Create distribution directory
mkdir -p dist
# Copy built frontend to dist
cp -r dist/* ../dist/

# Copy static files
cp -r public/* ../dist/

# Record build timestamp
echo "Built $(date -R)" > ../dist/BUILD_TIMESTAMP

# Done
echo "✅ Build finished: frontend and backend ready under 'dist/'"
