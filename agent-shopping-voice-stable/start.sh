#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Starting Bringo Chef AI servers..."

# Start backend API server (port 8080)
echo "Starting backend API on :8080..."
cd "$PROJECT_DIR"
python -m api.main &
BACKEND_PID=$!

# Wait for backend to be ready before starting frontend
echo "Waiting for backend to be ready..."
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health 2>/dev/null | grep -q "200"; then
        echo "Backend is ready!"
        break
    fi
    sleep 1
    WAITED=$((WAITED + 1))
    if [ $((WAITED % 5)) -eq 0 ]; then
        echo "  Still waiting... (${WAITED}s)"
    fi
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo "WARNING: Backend did not respond within ${MAX_WAIT}s, starting frontend anyway."
fi

# Start frontend dev server (port 3000)
echo "Starting frontend on :3000..."
cd "$PROJECT_DIR/app"
npm install --silent 2>/dev/null
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Servers running:"
echo "  Backend API : http://localhost:8080  (PID $BACKEND_PID)"
echo "  Frontend    : http://localhost:3000  (PID $FRONTEND_PID)"
echo ""
echo "Press Ctrl+C to stop both servers."

# Trap Ctrl+C to kill both processes
trap "echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

# Wait for either process to exit
wait
