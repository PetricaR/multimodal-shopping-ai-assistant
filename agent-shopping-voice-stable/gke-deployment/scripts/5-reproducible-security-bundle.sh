#!/bin/bash

# ========================================
# Bringo Multimodal API: Full Security Replication Script
# ========================================
# This script bundles Workload Identity and IAP setup into a single 
# reproducible flow.
#
# Usage: ./5-reproducible-security-bundle.sh <CLIENT_ID> <CLIENT_SECRET>

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check arguments
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <OAUTH_CLIENT_ID> <OAUTH_CLIENT_SECRET>"
    exit 1
fi

CLIENT_ID=$1
CLIENT_SECRET=$2

# Load configuration
if [ -f "config.env" ]; then
    source config.env
elif [ -f "../config.env" ]; then
    source ../config.env
fi

# 1. Setup Workload Identity (Non-interactive)
echo -e "${BLUE}=== Part 1: Workload Identity Setup ===${NC}"
bash 2-setup-workload-identity.sh

# 2. Configure OAuth Secret
echo -e "${BLUE}=== Part 2: Configuring OAuth Secrets ===${NC}"
kubectl create secret generic oauth-client-credentials \
    --from-literal=client_id=$CLIENT_ID \
    --from-literal=client_secret=$CLIENT_SECRET \
    -n ${K8S_NAMESPACE:-default} \
    --dry-run=client -o yaml | kubectl apply -f -
echo -e "${GREEN}✓ OAuth secret replicated${NC}"

# 3. Apply IAP Infrastructure
echo -e "${BLUE}=== Part 3: Applying IAP Infrastructure ===${NC}"
# We trigger the generation of manifests to ensure they are up to date
bash 0-generate-k8s-manifests.sh

# Reserve Global Static IP
echo "[INFO] Ensuring Global Static IP exists..."
if ! gcloud compute addresses describe ${APP_NAME:-bringo-multimodal-api}-ip --global --project=$GCP_PROJECT_ID &> /dev/null; then
    gcloud compute addresses create ${APP_NAME:-bringo-multimodal-api}-ip --global --project=$GCP_PROJECT_ID
fi

# Apply BackendConfig
cat <<EOF | kubectl apply -f -
apiVersion: cloud.google.com/v1
kind: BackendConfig
metadata:
  name: ${APP_NAME:-bringo-multimodal-api}-backend-config
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
EOF

# Update Service to use BackendConfig
kubectl annotate service ${APP_NAME:-bringo-multimodal-api} \
    cloud.google.com/backend-config='{"default": "'${APP_NAME:-bringo-multimodal-api}'-backend-config"}' \
    --overwrite

# Create Ingress
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ${APP_NAME:-bringo-multimodal-api}-ingress
  annotations:
    kubernetes.io/ingress.class: "gce"
    kubernetes.io/ingress.global-static-ip-name: "${APP_NAME:-bringo-multimodal-api}-ip"
spec:
  tls:
  - secretName: bringo-api-tls-secret
  rules:
  - http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: ${APP_NAME:-bringo-multimodal-api}
            port:
              number: 80
EOF

# 4. Grant IAP Permissions
echo -e "${BLUE}=== Part 4: Granting IAP IAM Permissions ===${NC}"
# Wait for backend service to be detectable
echo "[INFO] Waiting for Google Cloud to generate the Backend Service (can take 2 mins)..."
sleep 60

BACKEND_SERVICE=$(gcloud compute backend-services list --format="value(name)" --filter="name~${APP_NAME:-bringo-multimodal-api}" --project=$GCP_PROJECT_ID | head -n 1)

if [ -n "$BACKEND_SERVICE" ]; then
    echo "[INFO] Found Backend: $BACKEND_SERVICE"
    gcloud iap web add-iam-policy-binding \
        --resource-type=backend-services \
        --service=$BACKEND_SERVICE \
        --member="user:petrica.radan@formare.ai" \
        --role="roles/iap.httpsResourceAccessor" \
        --project=$GCP_PROJECT_ID
    echo -e "${GREEN}✓ IAP permissions granted to petrica.radan@formare.ai${NC}"
else
    echo -e "${YELLOW}[WARNING] Backend Service not found yet. Run the IAP binding command later.${NC}"
fi

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}SECURITY REPLICATION COMPLETE${NC}"
echo -e "${GREEN}========================================${NC}"
