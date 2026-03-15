#!/bin/bash

# ========================================
# Bringo Multimodal API: Security Debugging Script
# ========================================

set -e

# Load configuration
if [ -f "config.env" ]; then
    source config.env
elif [ -f "../config.env" ]; then
    source ../config.env
fi

APP_NAME="${APP_NAME:-bringo-multimodal-api}"

echo "🔎 Checking Workload Identity..."
kubectl get sa ${APP_NAME}-sa -o yaml | grep "iam.gke.io/gcp-service-account"

echo -e "\n🔎 Checking OAuth Secret..."
kubectl get secret oauth-client-credentials -n ${K8S_NAMESPACE:-default}

echo -e "\n🔎 Checking BackendConfig..."
kubectl get backendconfig ${APP_NAME}-backend-config -o yaml | grep -A 5 "iap:"

echo -e "\n🔎 Checking Service Annotations..."
kubectl get service ${APP_NAME} -o yaml | grep "backend-config"

echo -e "\n🔎 Checking Ingress Status..."
kubectl get ingress ${APP_NAME}-ingress

echo -e "\n🔎 Checking IAP IAM Binding..."
BACKEND_SERVICE=$(gcloud compute backend-services list --format="value(name)" --filter="name~${APP_NAME}" --project=$GCP_PROJECT_ID | head -n 1)
if [ -n "$BACKEND_SERVICE" ]; then
    gcloud iap web get-iam-policy --resource-type=backend-services --service=$BACKEND_SERVICE --project=$GCP_PROJECT_ID
else
    echo "Backend Service not found yet."
fi

echo -e "\n🔎 Testing Load Balancer Connectivity (Expected: 302 Redirect)..."
STATIC_IP=$(gcloud compute addresses describe ${APP_NAME}-ip --global --format="value(address)" --project=$GCP_PROJECT_ID)
curl -I http://$STATIC_IP
