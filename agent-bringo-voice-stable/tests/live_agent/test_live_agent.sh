#!/bin/bash
# Quick test script for Bringo Live AI Agent
# Usage: ./test_live_agent.sh

set -e
cd "$(dirname "$0")/../.."
echo "Current directory: $(pwd)"

echo "🧪 Bringo Live AI Agent - Quick Test Suite"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKEND_API="http://localhost:8080"
AGENT_DIR="agent/shop-agent"

check_service() {
    local url=$1
    local name=$2
    if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "200\|404"; then
        echo -e "${GREEN}✅ $name is running${NC}"
        return 0
    else
        echo -e "${RED}❌ $name is NOT running${NC}"
        return 1
    fi
}

# Test 1: Check if Backend API is running
echo "📡 Test 1: Backend API Status"
if check_service "$BACKEND_API" "Backend API"; then
    echo "   URL: $BACKEND_API"
else
    echo -e "${YELLOW}   ⚠️  Start backend with: python -m api.main${NC}"
fi
echo ""

# Test 2: Check authentication status
echo "🔐 Test 2: Authentication Status"
AUTH_RESPONSE=$(curl -s "$BACKEND_API/api/v1/auth/status" || echo '{"status":"error"}')
AUTH_STATUS=$(echo "$AUTH_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "error")

if [ "$AUTH_STATUS" = "authenticated" ]; then
    echo -e "${GREEN}✅ Session is active${NC}"
    USERNAME=$(echo "$AUTH_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('username', 'N/A'))" 2>/dev/null)
    echo "   User: $USERNAME"
elif [ "$AUTH_STATUS" = "not_authenticated" ] || [ "$AUTH_STATUS" = "expired" ]; then
    echo -e "${YELLOW}⚠️  Not authenticated${NC}"
    echo "   You need to login with Bringo credentials"
    echo ""
    echo "   Option 1: Set environment variables in .env:"
    echo "   BRINGO_USERNAME=your-email@example.com"
    echo "   BRINGO_PASSWORD=your-password"
    echo ""
    echo "   Option 2: Login via API:"
    echo "   curl -X POST $BACKEND_API/api/v1/auth/login \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{\"username\": \"YOUR_EMAIL\", \"password\": \"YOUR_PASSWORD\"}'"
else
    echo -e "${RED}❌ Authentication check failed${NC}"
    echo "   Response: $AUTH_RESPONSE"
fi
echo ""

# Test 3: Test product search
echo "🔍 Test 3: Product Search"
if [ "$AUTH_STATUS" = "authenticated" ]; then
    echo "   Searching for 'lapte'..."
    SEARCH_RESPONSE=$(curl -s -X POST "$BACKEND_API/api/v1/search" \
        -H "Content-Type: application/json" \
        -H "X-API-KEY: bringo_secure_shield_2026" \
        -d '{"query_text": "lapte", "top_k": 3, "use_ranking": true, "in_stock_only": true}' || echo '{"error": true}')
    
    if echo "$SEARCH_RESPONSE" | grep -q "similar_products"; then
        PRODUCT_COUNT=$(echo "$SEARCH_RESPONSE" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('similar_products', [])))" 2>/dev/null || echo "0")
        echo -e "${GREEN}✅ Search successful - Found $PRODUCT_COUNT products${NC}"
        
        # Show first product
        if [ "$PRODUCT_COUNT" -gt 0 ]; then
            FIRST_PRODUCT=$(echo "$SEARCH_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); p=data['similar_products'][0]; print(f\"{p.get('product_name', 'N/A')[:40]}... (Score: {p.get('ranking_score', 0):.2f})\")" 2>/dev/null || echo "N/A")
            echo "   Top result: $FIRST_PRODUCT"
        fi
    else
        echo -e "${RED}❌ Search failed${NC}"
        echo "   Response: $(echo "$SEARCH_RESPONSE" | head -c 100)"
    fi
else
    echo -e "${YELLOW}⚠️  Skipped (not authenticated)${NC}"
fi
echo ""

# Test 4: Check Live Agent
echo "🎤 Test 4: Live AI Agent"
if check_service "http://localhost:8000" "Live AI Agent"; then
    echo "   Frontend: http://localhost:8000"
    echo -e "${GREEN}✅ Ready for voice interaction${NC}"
else
    echo -e "${YELLOW}   ⚠️  Start agent with: cd $AGENT_DIR && make local-backend${NC}"
fi
echo ""

# Test 5: Check cart (if authenticated)
echo "🛒 Test 5: Cart Status"
if [ "$AUTH_STATUS" = "authenticated" ]; then
    CART_RESPONSE=$(curl -s "$BACKEND_API/api/v1/cart" || echo '{"error": true}')
    if echo "$CART_RESPONSE" | grep -q "cart_count"; then
        CART_COUNT=$(echo "$CART_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('cart_count', 0))" 2>/dev/null || echo "0")
        echo -e "${GREEN}✅ Cart accessible - $CART_COUNT items${NC}"
    else
        echo -e "${RED}❌ Cart check failed${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Skipped (not authenticated)${NC}"
fi
echo ""

# Summary
echo "=========================================="
echo "📊 Test Summary"
echo "=========================================="
echo ""
echo "Next Steps:"
echo ""
if [ "$AUTH_STATUS" != "authenticated" ]; then
    echo "1️⃣  Authenticate with Bringo:"
    echo "   - Set BRINGO_USERNAME and BRINGO_PASSWORD in .env, OR"
    echo "   - Call POST /api/v1/auth/login with credentials"
    echo ""
fi
echo "2️⃣  Test voice interaction:"
echo "   - Open http://localhost:8000"
echo "   - Click play button"
echo "   - Try: 'Caut lapte' (search for milk)"
echo ""
echo "3️⃣  Test cart operations:"
echo "   - Voice: 'Adaugă primul produs în coș'"
echo "   - Verify at www.bringo.ro"
echo ""
echo "📖 Full test plan: TEST_PLAN_LIVE_AGENT.md"
echo ""
