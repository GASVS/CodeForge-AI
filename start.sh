#!/bin/bash
# Jev Open Source Dashboard - Startup Script

set -e

PROJECT_DIR="/home/andrej/Desktop/App/jev-opensource-dashboard"
BACKEND_DIR="$PROJECT_DIR/src/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$PROJECT_DIR/venv"

echo "🚀 Starting Jev Open Source Dashboard..."
echo ""

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "❌ Ollama not running. Starting it..."
    ollama serve &
    sleep 3
fi

echo "✅ Ollama detected"

# Kill existing servers on ports 8001 and 3000
kill $(lsof -ti:8001) 2>/dev/null || true
kill $(lsof -ti:3000) 2>/dev/null || true
sleep 1

echo "📂 Project directory: $PROJECT_DIR"
echo ""

# Activate venv and start backend
cd "$BACKEND_DIR"
source "$VENV_DIR/bin/activate"

echo "🎨 Backend API on http://localhost:8001"
echo "💬 Frontend UI on http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop all services"
echo "---"
echo ""

# Start backend in background
uvicorn main:app --host 0.0.0.0 --port 8001 &
BACKEND_PID=$!

sleep 2

# Verify backend started
if curl -s http://localhost:8001/health | grep -q "healthy"; then
    echo "✅ Backend running"
else
    echo "❌ Failed to start backend"
    kill $BACKEND_PID
    exit 1
fi

# Start frontend in background
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

echo "✅ Frontend starting..."
sleep 3
echo ""
echo "🎉 Dashboard ready! Open http://localhost:3000 in your browser"
echo ""

# Wait for user to interrupt
wait
