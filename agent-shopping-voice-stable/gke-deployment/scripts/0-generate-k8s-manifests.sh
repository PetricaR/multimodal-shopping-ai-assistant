#!/bin/bash

# Generate Kubernetes YAML Files
# ================================
# This script automatically generates Kubernetes manifests for your ADK agent

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# Load configuration
if [ -f "../config.env" ]; then
    source ../config.env
fi

# Configuration with defaults
APP_NAME="${APP_NAME:-bringo-multimodal-api}"
NAMESPACE="${K8S_NAMESPACE:-default}"
REPLICAS="${REPLICAS:-2}"
PORT="${PORT:-8080}"
MEMORY_REQUEST="${MEMORY_REQUEST:-512Mi}"
MEMORY_LIMIT="${MEMORY_LIMIT:-1Gi}"
CPU_REQUEST="${CPU_REQUEST:-500m}"
CPU_LIMIT="${CPU_LIMIT:-1000m}"

# Create k8s directory if it doesn't exist
mkdir -p ../k8s

print_header "Generating Kubernetes Manifests"

print_info "Configuration:"
echo "  App Name:       $APP_NAME"
echo "  Namespace:      $NAMESPACE"
echo "  Replicas:       $REPLICAS"
echo "  Port:           $PORT"
echo "  Memory Request: $MEMORY_REQUEST"
echo "  Memory Limit:   $MEMORY_LIMIT"
echo "  CPU Request:    $CPU_REQUEST"
echo "  CPU Limit:      $CPU_LIMIT"
echo ""

# Generate deployment.yaml
print_info "Generating deployment.yaml..."

cat > ../k8s/deployment.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${APP_NAME}
  labels:
    app: ${APP_NAME}
spec:
  replicas: ${REPLICAS}
  selector:
    matchLabels:
      app: ${APP_NAME}
  template:
    metadata:
      labels:
        app: ${APP_NAME}
    spec:
      serviceAccountName: ${APP_NAME}-sa
      containers:
      - name: ${APP_NAME}
        image: IMAGE_URL_PLACEHOLDER
        ports:
        - containerPort: ${PORT}
          protocol: TCP
        env:
        - name: PORT
          value: "${PORT}"
        - name: PYTHONUNBUFFERED
          value: "1"
        - name: PROJECT_ID
          value: "${GCP_PROJECT_ID}"
        - name: LOCATION
          value: "${AI_LOCATION}"
        - name: STAGING_BUCKET
          value: "formare-ai-vector-search"
        - name: API_AUTH_KEY
          value: "${API_AUTH_KEY:-no-key-set}"
        resources:
          requests:
            memory: "${MEMORY_REQUEST}"
            cpu: "${CPU_REQUEST}"
          limits:
            memory: "${MEMORY_LIMIT}"
            cpu: "${CPU_LIMIT}"
        livenessProbe:
          httpGet:
            path: /health
            port: ${PORT}
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: ${PORT}
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
EOF

# Generate service.yaml
print_info "Generating service.yaml..."

# Check if IAP is enabled in config or env
if [[ "$IAP_ENABLED" == "true" ]]; then
    SERVICE_TYPE="ClusterIP"
    SERVICE_ANNOTATIONS="  annotations:
    cloud.google.com/backend-config: '{\"default\": \"${APP_NAME}-backend-config\"}'
    cloud.google.com/neg: '{\"ingress\": true}'"
    SERVICE_SPEC=""
else
    SERVICE_TYPE="LoadBalancer"
    SERVICE_ANNOTATIONS=""
    # Fixed: Remove leading spaces since heredoc already indents with 2 spaces
    if [ -n "${LOADBALANCER_IP}" ]; then
        SERVICE_SPEC="loadBalancerIP: \"${LOADBALANCER_IP}\""
    else
        SERVICE_SPEC=""
    fi
fi

cat > ../k8s/service.yaml <<EOF
apiVersion: v1
kind: Service
metadata:
  name: ${APP_NAME}
  labels:
    app: ${APP_NAME}
${SERVICE_ANNOTATIONS}
spec:
  type: ${SERVICE_TYPE}
  ${SERVICE_SPEC}
  selector:
    app: ${APP_NAME}
  ports:
  - name: http
    port: 80
    targetPort: ${PORT}
    protocol: TCP
EOF

print_info "✓ Generated: ../k8s/deployment.yaml"
print_info "✓ Generated: ../k8s/service.yaml"

echo ""
print_info "Kubernetes manifests created successfully!"
echo ""
echo "Files created:"
echo "  - gke-deployment/k8s/deployment.yaml"
echo "  - gke-deployment/k8s/service.yaml"
echo ""
echo "To customize, edit config.env and run this script again, or edit the YAML files directly."