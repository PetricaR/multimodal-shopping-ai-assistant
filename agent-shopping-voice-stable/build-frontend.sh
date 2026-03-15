#!/bin/bash

echo "🔨 Building Bringo Frontend..."
cd /Users/radanpetrica/PFA/agents/agents-adk-mcp/ai_agents/agent-bringo/app

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install --silent 2>/dev/null || {
        echo "❌ npm not found. Using pre-built dist if available."
        exit 0
    }
fi

echo "🏗️ Building with Vite..."
npm run build 2>&1 | tail -20

if [ -d "dist" ]; then
    echo "✅ Build complete!"
    echo "📂 Frontend ready at: ./dist/"
else
    echo "⚠️  dist folder not found"
fi
