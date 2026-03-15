#!/bin/bash

echo "🔍 Testing Bringo API Startup Configuration..."
cd "$(dirname "$0")/../.."
echo "Current directory: $(pwd)"
echo ""

# 1. Check .env file
echo "1️⃣  Checking .env file..."
if [ -f ".env" ]; then
    echo "   ✓ .env file exists"
    GOOGLE_KEY=$(grep "GOOGLE_API_KEY=" .env | cut -d'=' -f2 | tr -d '"')
    if [ -n "$GOOGLE_KEY" ]; then
        echo "   ✓ GOOGLE_API_KEY is set: ${GOOGLE_KEY:0:20}..."
    else
        echo "   ✗ GOOGLE_API_KEY is not set in .env"
    fi
else
    echo "   ✗ .env file not found"
fi

echo ""

# 2. Check Python environment
echo "2️⃣  Checking Python environment..."
VENV_DIR="/Users/radanpetrica/PFA/agents/agents-adk-mcp/ai_env"
if [ -f "$VENV_DIR/bin/activate" ]; then
    echo "   ✓ Virtual environment found"
    source "$VENV_DIR/bin/activate"
    echo "   ✓ Virtual environment activated"
    python --version
else
    echo "   ✗ Virtual environment not found"
    exit 1
fi

echo ""

# 3. Check required packages
echo "3️⃣  Checking required packages..."
python -c "import fastapi; print('   ✓ fastapi installed')" 2>/dev/null || echo "   ✗ fastapi not installed"
python -c "import uvicorn; print('   ✓ uvicorn installed')" 2>/dev/null || echo "   ✗ uvicorn not installed"
python -c "from api.main import app; print('   ✓ api.main can be imported')" 2>/dev/null || echo "   ✗ api.main import failed"

echo ""

# 4. Clean up existing processes
echo "4️⃣  Cleaning up existing processes..."
pkill -f "python.*api.main" 2>/dev/null && echo "   ✓ Killed existing API processes" || echo "   - No existing API processes"
pkill -f "npm.*dev" 2>/dev/null && echo "   ✓ Killed existing npm processes" || echo "   - No existing npm processes"
sleep 2

# 5. Try to start API
echo ""
echo "5️⃣  Starting API server (timeout 10s)..."
timeout 10 python -m api.main &
API_PID=$!

sleep 3

# 6. Check if API is responding
echo ""
echo "6️⃣  Checking API response..."
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "   ✓ API is responding on /health"
    
    CONFIG_RESPONSE=$(curl -s http://localhost:8080/api/v1/config)
    echo "   ✓ API config response: $CONFIG_RESPONSE"
    
    # Check if the API key matches
    if echo "$CONFIG_RESPONSE" | grep "$GOOGLE_KEY" > /dev/null; then
        echo "   ✓ Config has the correct API key!"
    else
        echo "   ⚠️  Config API key might be different"
    fi
else
    echo "   ✗ API is not responding"
fi

echo ""
echo "✅ Test complete!"

# Clean up
kill $API_PID 2>/dev/null || true
