#!/bin/bash

# Quick IAP Verification
# ======================

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_ID="formare-ai"
APP_NAME="bringo-multimodal-api"
INGRESS_IP="34.78.177.35"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}IAP Quick Verification${NC}"
echo -e "${BLUE}========================================${NC}\n"

# 1. Check Backend Service
echo -e "${YELLOW}1. Checking Backend Service...${NC}"
BACKEND_SERVICE=$(gcloud compute backend-services list \
  --filter="name~${APP_NAME}" \
  --format="value(name)" \
  --project=$PROJECT_ID 2>/dev/null | head -n 1)

if [ -n "$BACKEND_SERVICE" ]; then
    echo -e "${GREEN}✓${NC} Backend service found: ${BACKEND_SERVICE}"
    
    # Check IAP status
    echo -e "\n${YELLOW}2. Checking IAP Configuration...${NC}"
    IAP_POLICY=$(gcloud iap web get-iam-policy \
        --resource-type=backend-services \
        --service=$BACKEND_SERVICE \
        --project=$PROJECT_ID 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} IAP policy configured"
        
        # Extract authorized users
        USERS=$(echo "$IAP_POLICY" | grep -A 100 "role: roles/iap.httpsResourceAccessor" | grep "user:" | sed 's/.*user://' | tr -d ' ')
        
        if [ -n "$USERS" ]; then
            echo -e "${GREEN}✓${NC} Authorized users:"
            echo "$USERS" | while read -r user; do
                echo "    - $user"
            done
        else
            echo -e "${RED}✗${NC} No users authorized yet!"
            echo ""
            echo "Grant access with:"
            echo "  gcloud iap web add-iam-policy-binding \\"
            echo "    --resource-type=backend-services \\"
            echo "    --service=$BACKEND_SERVICE \\"
            echo "    --member='user:petrica.radan@formare.ai' \\"
            echo "    --role='roles/iap.httpsResourceAccessor' \\"
            echo "    --project=$PROJECT_ID"
        fi
    else
        echo -e "${YELLOW}⚠${NC} IAP policy not ready yet (wait 2-3 minutes)"
    fi
    
    # Check backend health
    echo -e "\n${YELLOW}3. Checking Backend Health...${NC}"
    HEALTH=$(gcloud compute backend-services get-health $BACKEND_SERVICE \
        --global \
        --project=$PROJECT_ID 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        HEALTHY_COUNT=$(echo "$HEALTH" | grep "HEALTHY" | wc -l)
        if [ $HEALTHY_COUNT -gt 0 ]; then
            echo -e "${GREEN}✓${NC} Backend is healthy ($HEALTHY_COUNT healthy backends)"
        else
            echo -e "${YELLOW}⚠${NC} Backend health check status:"
            echo "$HEALTH"
        fi
    else
        echo -e "${YELLOW}⚠${NC} Health check not ready yet"
    fi
else
    echo -e "${YELLOW}⚠${NC} Backend service not found yet"
    echo "    This typically takes 5-10 minutes after Ingress creation"
    echo "    Wait a few minutes and run this script again"
fi

# 4. Test Access
echo -e "\n${YELLOW}4. Testing Access...${NC}"
echo "Testing: http://${INGRESS_IP}/health"
echo ""

RESPONSE=$(curl -s -w "\n%{http_code}" "http://${INGRESS_IP}/health" 2>&1)
HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | head -n -1)

case $HTTP_CODE in
    302)
        echo -e "${GREEN}✓${NC} IAP is working! (Received redirect to Google login)"
        REDIRECT_URL=$(echo "$BODY" | grep -o 'https://accounts.google.com[^"]*' | head -n 1)
        if [ -n "$REDIRECT_URL" ]; then
            echo "    Redirects to: ${REDIRECT_URL:0:60}..."
        fi
        echo ""
        echo -e "${GREEN}SUCCESS: IAP is fully operational!${NC}"
        ;;
    200)
        echo -e "${YELLOW}⚠${NC} Received HTTP 200 (IAP may not be active yet)"
        echo "    Response: $BODY"
        echo "    Wait 2-3 minutes for IAP to activate"
        ;;
    403)
        echo -e "${YELLOW}⚠${NC} Received HTTP 403 (Forbidden)"
        echo "    IAP is active but access may not be configured"
        ;;
    404)
        echo -e "${RED}✗${NC} Received HTTP 404 (Not Found)"
        echo "    Check if your application is running"
        ;;
    000)
        echo -e "${RED}✗${NC} Could not connect to $INGRESS_IP"
        echo "    The Ingress may still be provisioning"
        ;;
    *)
        echo -e "${YELLOW}⚠${NC} Received HTTP $HTTP_CODE"
        echo "    Response: $BODY"
        ;;
esac

# Summary
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}Summary${NC}"
echo -e "${BLUE}========================================${NC}\n"

echo "Access URL: ${GREEN}http://${INGRESS_IP}${NC}"
echo ""

if [ $HTTP_CODE -eq 302 ]; then
    echo -e "${GREEN}✓ IAP is fully operational!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Open http://${INGRESS_IP} in your browser"
    echo "  2. You'll be redirected to Google login"
    echo "  3. Sign in with an authorized email"
    echo "  4. You'll be granted access to the API"
    echo ""
    echo "Test endpoints:"
    echo "  • Health:    http://${INGRESS_IP}/health"
    echo "  • API Docs:  http://${INGRESS_IP}/docs"
    echo "  • Info:      http://${INGRESS_IP}/info"
elif [ -z "$BACKEND_SERVICE" ]; then
    echo -e "${YELLOW}⚠ Backend service still provisioning${NC}"
    echo ""
    echo "Wait 5-10 minutes, then run this script again"
elif [ -z "$USERS" ]; then
    echo -e "${YELLOW}⚠ No users authorized yet${NC}"
    echo ""
    echo "Grant access to your email:"
    echo "  gcloud iap web add-iam-policy-binding \\"
    echo "    --resource-type=backend-services \\"
    echo "    --service=$BACKEND_SERVICE \\"
    echo "    --member='user:petrica.radan@formare.ai' \\"
    echo "    --role='roles/iap.httpsResourceAccessor' \\"
    echo "    --project=$PROJECT_ID"
else
    echo -e "${YELLOW}⚠ IAP still activating${NC}"
    echo ""
    echo "Wait 2-3 more minutes for IAP to fully activate"
    echo "Then try accessing: http://${INGRESS_IP}"
fi

echo ""
echo "For detailed status, run: ./check-iap-status.sh"