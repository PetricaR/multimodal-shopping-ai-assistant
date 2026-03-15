#!/bin/bash

# Identity-Aware Proxy (IAP) Setup Script
# ========================================
# Secures your application with Google authentication
# Only allows access to specific email addresses

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Load configuration
if [ -f "../config.env" ]; then
    source ../config.env
fi

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-formare-ai}"
APP_NAME="${APP_NAME:-bringo-multimodal-api}"
NAMESPACE="${K8S_NAMESPACE:-default}"
REGION="${GCP_REGION:-europe-west4}"
CLUSTER_NAME="${CLUSTER_NAME:-cluster-ai-agents}"

# Allowed emails (edit this list)
ALLOWED_EMAILS=(
    "petrica.radan@formare.ai"
    # Add more emails here:
    # "user2@formare.ai"
    # "user3@formare.ai"
)

# ========================================
# Prerequisites Check
# ========================================

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check if kubectl is configured
    if ! kubectl cluster-info &> /dev/null; then
        print_error "kubectl is not configured. Run: gcloud container clusters get-credentials $CLUSTER_NAME --region=$REGION"
        exit 1
    fi
    
    # Check if deployment exists
    if ! kubectl get deployment $APP_NAME -n $NAMESPACE &> /dev/null; then
        print_error "Deployment '$APP_NAME' not found in namespace '$NAMESPACE'"
        echo "Please deploy the application first."
        exit 1
    fi
    
    print_success "Prerequisites met"
}

# ========================================
# Main Setup
# ========================================

print_header "IAP Security Setup"

echo "This script will:"
echo "  1. Enable required APIs"
echo "  2. Reserve static IP address"
echo "  3. Create OAuth credentials (requires manual OAuth consent screen setup)"
echo "  4. Configure Kubernetes resources for IAP"
echo "  5. Grant access to specific email addresses"
echo ""
echo "Allowed emails:"
for email in "${ALLOWED_EMAILS[@]}"; do
    echo "  - $email"
done
echo ""

read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Aborted"
    exit 0
fi

check_prerequisites

# Step 1: Enable Required APIs
print_header "Step 1: Enable Required APIs"
print_info "Enabling IAP and Compute APIs..."
gcloud services enable iap.googleapis.com --project=$PROJECT_ID
gcloud services enable compute.googleapis.com --project=$PROJECT_ID
gcloud services enable certificatemanager.googleapis.com --project=$PROJECT_ID
print_success "APIs enabled"

# Step 2: Reserve Static IP
print_header "Step 2: Reserve Static IP"
print_info "Checking for existing static IP..."
if ! gcloud compute addresses describe ${APP_NAME}-ip --global --project=$PROJECT_ID &> /dev/null; then
    print_info "Creating new static IP..."
    gcloud compute addresses create ${APP_NAME}-ip --global --project=$PROJECT_ID
    print_success "Static IP reserved"
else
    print_info "Static IP already exists"
fi

STATIC_IP=$(gcloud compute addresses describe ${APP_NAME}-ip --global --format="value(address)" --project=$PROJECT_ID)
print_info "Static IP: $STATIC_IP"

# Step 3: OAuth Setup Instructions
print_header "Step 3: OAuth Consent Screen Setup"
print_warning "MANUAL SETUP REQUIRED - Please complete these steps:"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Create OAuth Consent Screen:"
echo "   URL: https://console.cloud.google.com/apis/credentials/consent?project=$PROJECT_ID"
echo ""
echo "   Settings:"
echo "   - User Type: Internal (for @formare.ai domain only)"
echo "   - App name: Bringo Multimodal API"
echo "   - User support email: ${ALLOWED_EMAILS[0]}"
echo "   - Developer contact: ${ALLOWED_EMAILS[0]}"
echo ""
echo "2. Create OAuth 2.0 Client ID:"
echo "   URL: https://console.cloud.google.com/apis/credentials?project=$PROJECT_ID"
echo ""
echo "   Settings:"
echo "   - Click 'Create Credentials' → 'OAuth client ID'"
echo "   - Application type: Web application"
echo "   - Name: IAP-Client-${APP_NAME}"
echo "   - Authorized redirect URIs will be auto-configured by IAP"
echo ""
echo "3. Copy the Client ID and Client Secret"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
print_warning "After completing the OAuth setup, press Enter to continue..."
read

# Step 4: Get OAuth Credentials
print_header "Step 4: OAuth Credentials"
echo "Enter your OAuth Client ID:"
read CLIENT_ID

if [ -z "$CLIENT_ID" ]; then
    print_error "Client ID cannot be empty"
    exit 1
fi

echo "Enter your OAuth Client Secret:"
read -s CLIENT_SECRET
echo ""

if [ -z "$CLIENT_SECRET" ]; then
    print_error "Client Secret cannot be empty"
    exit 1
fi

# Create Kubernetes secret
print_info "Creating Kubernetes OAuth secret..."
kubectl create secret generic oauth-client-credentials \
    --from-literal=client_id=$CLIENT_ID \
    --from-literal=client_secret=$CLIENT_SECRET \
    -n $NAMESPACE \
    --dry-run=client -o yaml | kubectl apply -f -
print_success "OAuth secret created"

# Step 5: Create BackendConfig
print_header "Step 5: Create IAP BackendConfig"

print_info "Creating BackendConfig with IAP enabled..."
cat > /tmp/backend-config.yaml <<EOF
apiVersion: cloud.google.com/v1
kind: BackendConfig
metadata:
  name: ${APP_NAME}-backend-config
  namespace: $NAMESPACE
spec:
  iap:
    enabled: true
    oauthclientCredentials:
      secretName: oauth-client-credentials
  healthCheck:
    checkIntervalSec: 10
    port: 8080
    type: HTTP
    requestPath: /health
  timeoutSec: 30
  connectionDraining:
    drainingTimeoutSec: 60
EOF

kubectl apply -f /tmp/backend-config.yaml
print_success "BackendConfig created"

# Step 6: Update Service to ClusterIP
print_header "Step 6: Update Service Configuration"

print_info "Converting service to ClusterIP for IAP..."
cat > /tmp/service-iap.yaml <<EOF
apiVersion: v1
kind: Service
metadata:
  name: $APP_NAME
  namespace: $NAMESPACE
  annotations:
    cloud.google.com/backend-config: '{"default": "${APP_NAME}-backend-config"}'
    cloud.google.com/neg: '{"ingress": true}'
spec:
  type: ClusterIP
  selector:
    app: $APP_NAME
  ports:
  - name: http
    port: 80
    targetPort: 8080
    protocol: TCP
EOF

kubectl apply -f /tmp/service-iap.yaml
print_success "Service updated to ClusterIP"

# Step 7: Create Ingress with Fixed Annotations
print_header "Step 7: Create Ingress"

print_info "Creating Ingress with IAP configuration..."
cat > /tmp/ingress-iap.yaml <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ${APP_NAME}-ingress
  namespace: $NAMESPACE
  annotations:
    # Use ingressClassName instead of deprecated annotation
    networking.gke.io/managed-certificates: "${APP_NAME}-cert"
    kubernetes.io/ingress.global-static-ip-name: "${APP_NAME}-ip"
spec:
  ingressClassName: gce
  defaultBackend:
    service:
      name: $APP_NAME
      port:
        number: 80
EOF

kubectl apply -f /tmp/ingress-iap.yaml
print_success "Ingress created"

# Step 8: Create ManagedCertificate (Optional - for HTTPS)
print_header "Step 8: SSL Certificate (Optional)"

read -p "Do you want to set up HTTPS with a custom domain? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Enter your domain (e.g., api.formare.ai):"
    read DOMAIN_NAME
    
    if [ -n "$DOMAIN_NAME" ]; then
        print_info "Creating ManagedCertificate for $DOMAIN_NAME..."
        cat > /tmp/managed-cert.yaml <<EOF
apiVersion: networking.gke.io/v1
kind: ManagedCertificate
metadata:
  name: ${APP_NAME}-cert
  namespace: $NAMESPACE
spec:
  domains:
    - $DOMAIN_NAME
EOF
        
        kubectl apply -f /tmp/managed-cert.yaml
        print_success "ManagedCertificate created for $DOMAIN_NAME"
        print_warning "Don't forget to point $DOMAIN_NAME to $STATIC_IP in your DNS settings"
    fi
else
    print_info "Skipping HTTPS setup. Using HTTP only."
fi

# Step 9: Wait for Ingress
print_header "Step 9: Waiting for Ingress"

print_info "Waiting for Ingress to be provisioned..."
print_warning "This typically takes 5-10 minutes. You can Ctrl+C to skip waiting."

# Wait for ingress to get an IP
for i in {1..60}; do
    INGRESS_IP=$(kubectl get ingress ${APP_NAME}-ingress -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
    if [ -n "$INGRESS_IP" ]; then
        print_success "Ingress IP assigned: $INGRESS_IP"
        break
    fi
    echo -n "."
    sleep 5
done
echo ""

if [ -z "$INGRESS_IP" ]; then
    print_warning "Ingress IP not yet assigned. Check status with:"
    echo "  kubectl get ingress ${APP_NAME}-ingress -n $NAMESPACE"
fi

# Step 10: Grant Access to Users
print_header "Step 10: Grant IAP Access to Users"

print_info "Waiting for backend service to be created (30 seconds)..."
sleep 30

# Find backend service
BACKEND_SERVICE=$(gcloud compute backend-services list \
    --format="value(name)" \
    --filter="name~${APP_NAME}" \
    --project=$PROJECT_ID 2>/dev/null | head -n 1)

if [ -z "$BACKEND_SERVICE" ]; then
    print_warning "Backend service not found yet. It may still be creating."
    echo ""
    print_info "Run these commands manually after a few minutes:"
    echo ""
    for email in "${ALLOWED_EMAILS[@]}"; do
        echo "# Grant access to $email"
        echo "gcloud iap web add-iam-policy-binding \\"
        echo "  --resource-type=backend-services \\"
        echo "  --service=<BACKEND_SERVICE_NAME> \\"
        echo "  --member='user:$email' \\"
        echo "  --role='roles/iap.httpsResourceAccessor' \\"
        echo "  --project=$PROJECT_ID"
        echo ""
    done
else
    print_info "Backend service found: $BACKEND_SERVICE"
    print_info "Granting IAP access to users..."
    
    for email in "${ALLOWED_EMAILS[@]}"; do
        print_info "Granting access to: $email"
        gcloud iap web add-iam-policy-binding \
            --resource-type=backend-services \
            --service=$BACKEND_SERVICE \
            --member="user:$email" \
            --role="roles/iap.httpsResourceAccessor" \
            --project=$PROJECT_ID 2>/dev/null || {
            print_warning "Failed to grant access to $email. You may need to wait longer or run this manually."
        }
    done
    
    print_success "Access granted to all users"
fi

# ========================================
# Summary
# ========================================

print_header "Setup Complete!"

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ IAP is now enabled${NC}"
echo -e "${GREEN}✓ Static IP: ${NC}$STATIC_IP"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Authorized users:"
for email in "${ALLOWED_EMAILS[@]}"; do
    echo "  ✓ $email"
done
echo ""
print_info "Access URL: http://$STATIC_IP"
print_info "Users will be prompted to sign in with Google"
print_info "Only authorized emails can access the application"
echo ""
print_warning "Important: It may take 5-10 minutes for IAP to be fully active"
echo ""

# Useful commands
echo -e "${YELLOW}Useful Commands:${NC}"
echo ""
echo "Check Ingress status:"
echo "  kubectl get ingress ${APP_NAME}-ingress -n $NAMESPACE"
echo ""
echo "Check BackendConfig:"
echo "  kubectl describe backendconfig ${APP_NAME}-backend-config -n $NAMESPACE"
echo ""
echo "View IAP logs:"
echo "  gcloud logging read 'resource.type=http_load_balancer' --limit 50 --project=$PROJECT_ID"
echo ""
echo "Add more users:"
if [ -n "$BACKEND_SERVICE" ]; then
    echo "  gcloud iap web add-iam-policy-binding \\"
    echo "    --resource-type=backend-services \\"
    echo "    --service=$BACKEND_SERVICE \\"
    echo "    --member='user:new.user@formare.ai' \\"
    echo "    --role='roles/iap.httpsResourceAccessor' \\"
    echo "    --project=$PROJECT_ID"
else
    echo "  (Wait for backend service to be created, then use the command shown above)"
fi
echo ""
echo "Remove user access:"
if [ -n "$BACKEND_SERVICE" ]; then
    echo "  gcloud iap web remove-iam-policy-binding \\"
    echo "    --resource-type=backend-services \\"
    echo "    --service=$BACKEND_SERVICE \\"
    echo "    --member='user:email@formare.ai' \\"
    echo "    --role='roles/iap.httpsResourceAccessor' \\"
    echo "    --project=$PROJECT_ID"
fi

# Cleanup temp files
rm -f /tmp/backend-config.yaml /tmp/service-iap.yaml /tmp/ingress-iap.yaml /tmp/managed-cert.yaml

print_success "IAP setup complete!"