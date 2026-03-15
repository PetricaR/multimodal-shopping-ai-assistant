#!/bin/bash

# GKE Cluster IP Discovery Script
# ==============================
# This script identifies and displays all public endpoints 
# for the cluster and its services.

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-formare-ai}"
REGION="${GCP_REGION:-europe-west1}"
CLUSTER_NAME="${CLUSTER_NAME:-ai-agents-cluster}"
NAMESPACE="${K8S_NAMESPACE:-default}"

print_header "GKE Cluster IP Discovery"

echo "Context:"
echo "  Project:   $PROJECT_ID"
echo "  Cluster:   $CLUSTER_NAME"
echo "  Region:    $REGION"
echo ""

# 1. Cluster API Server Endpoint
print_info "Retrieving Cluster API Endpoint..."
ENDPOINT=$(gcloud container clusters describe "$CLUSTER_NAME" --region="$REGION" --project="$PROJECT_ID" --format="value(endpoint)" 2>/dev/null || echo "Not found")
echo -e "${YELLOW}Cluster API Endpoint:${NC} $ENDPOINT"

# 2. LoadBalancer Services
print_header "LoadBalancer Services"
kubectl get services -n "$NAMESPACE" -o custom-columns=NAME:.metadata.name,TYPE:.spec.type,EXTERNAL-IP:.status.loadBalancer.ingress[0].ip | grep -v "none"

# 3. Ingresses
print_header "Ingresses"
kubectl get ingress -n "$NAMESPACE" -o custom-columns=NAME:.metadata.name,ADDRESS:.status.loadBalancer.ingress[0].ip | grep -v "none"

# 4. Global Gateways (if any)
if kubectl get gateway &> /dev/null; then
    print_header "Gateways (Gateway API)"
    kubectl get gateway -n "$NAMESPACE" -o custom-columns=NAME:.metadata.name,ADDRESS:.status.addresses[0].value | grep -v "none"
fi

print_header "Summary"
echo "To access your primary application, use the IP listed under LoadBalancer Services."
echo "If you are using IAP/Ingress, use the Address listed under Ingresses."
