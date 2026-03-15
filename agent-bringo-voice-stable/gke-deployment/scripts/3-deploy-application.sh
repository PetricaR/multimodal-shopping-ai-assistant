#!/bin/bash

# Application Deployment Script
# ==============================
# Complete deployment pipeline for deploying to GKE

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =======================================
# Configuration
# =======================================

PROJECT_ID="${GCP_PROJECT_ID:-formare-ai}"
REGION="${GCP_REGION:-europe-west1}"
CLUSTER_NAME="${CLUSTER_NAME:-ai-agents-cluster}"

# Application Configuration
APP_NAME="${APP_NAME:-bringo-multimodal-api}"
IMAGE_NAME="$APP_NAME"
SERVICE_NAME="$APP_NAME"
NAMESPACE="${K8S_NAMESPACE:-default}"

# Registry Configuration
REGISTRY_TYPE="${REGISTRY_TYPE:-gcr}"
AR_LOCATION="${AR_LOCATION:-$REGION}"
AR_REPOSITORY="${AR_REPOSITORY:-docker-repo}"

# Build Configuration
BUILD_CONTEXT="../.."
DEPLOYMENT_DIR="../k8s"

# =======================================
# Helper Functions
# =======================================

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

# Wait for External IP
wait_for_external_ip() {
    local service="${1:-$SERVICE_NAME}"
    local ns="${2:-$NAMESPACE}"
    local timeout=300
    local interval=10
    local elapsed=0
    
    print_info "Waiting for external IP for service $service in namespace $ns..."
    
    while [ $elapsed -lt "$timeout" ]; do
        local ip=$(kubectl get service "$service" -n "$ns" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
        if [ -n "$ip" ]; then
            echo "$ip"
            return 0
        fi
        
        sleep "$interval"
        elapsed=$((elapsed + interval))
        print_info "Still waiting... ($elapsed/${timeout}s)"
    done
    
    return 1
}

# =======================================
# Check Prerequisites
# =======================================

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed"
        exit 1
    fi
    
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed"
        exit 1
    fi
    
    print_success "All prerequisites met"
}

# =======================================
# Get Image URL
# =======================================

get_image_url() {
    local tag=$1
    
    if [ "$REGISTRY_TYPE" == "gcr" ]; then
        echo "gcr.io/${PROJECT_ID}/${IMAGE_NAME}:${tag}"
    elif [ "$REGISTRY_TYPE" == "artifact-registry" ]; then
        echo "${AR_LOCATION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}:${tag}"
    fi
}

# =======================================
# Configure Docker Authentication
# =======================================

configure_docker_auth() {
    print_header "Configuring Docker Authentication"
    
    if [ "$REGISTRY_TYPE" == "gcr" ]; then
        gcloud auth configure-docker --quiet
    elif [ "$REGISTRY_TYPE" == "artifact-registry" ]; then
        gcloud auth configure-docker ${AR_LOCATION}-docker.pkg.dev --quiet
    fi
    
    print_success "Docker authentication configured"
}

# =======================================
# Build Docker Image
# =======================================

build_image() {
    print_header "Building Docker Image"
    
    local tag=$(date +%Y%m%d-%H%M%S)
    local image_url=$(get_image_url "$tag")
    local latest_url=$(get_image_url "latest")
    
    print_info "Building for platform: linux/amd64"
    print_info "Image: $image_url"
    
    docker build \
        --platform=linux/amd64 \
        -t "$image_url" \
        -t "$latest_url" \
        "$BUILD_CONTEXT"
    
    export IMAGE_TAG="$tag"
    export IMAGE_URL="$image_url"
    export LATEST_URL="$latest_url"
    
    print_success "Docker image built"
}

# =======================================
# Push Docker Image
# =======================================

push_image() {
    print_header "Pushing Docker Image"
    
    print_info "Pushing $IMAGE_URL"
    docker push "$IMAGE_URL"
    
    print_info "Pushing $LATEST_URL"
    docker push "$LATEST_URL"
    
    print_success "Docker image pushed"
}

# =======================================
# Get Cluster Credentials
# =======================================

get_cluster_credentials() {
    print_header "Getting Cluster Credentials"
    
    gcloud container clusters get-credentials "$CLUSTER_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID"
    
    print_success "Credentials obtained"
}

# =======================================
# Deploy to Kubernetes
# =======================================

deploy_to_kubernetes() {
    print_header "Deploying to Kubernetes"
    
    # Apply deployment
    if [ -f "$DEPLOYMENT_DIR/deployment.yaml" ]; then
        print_info "Applying deployment..."
        cat "$DEPLOYMENT_DIR/deployment.yaml" | \
            sed "s|IMAGE_URL_PLACEHOLDER|$IMAGE_URL|g" | \
            kubectl apply -n "$NAMESPACE" -f -
    else
        print_error "Deployment file not found: $DEPLOYMENT_DIR/deployment.yaml"
        exit 1
    fi
    
    # Apply service
    if [ -f "$DEPLOYMENT_DIR/service.yaml" ]; then
        print_info "Applying service..."
        kubectl apply -n "$NAMESPACE" -f "$DEPLOYMENT_DIR/service.yaml"
    fi
    
    print_success "Kubernetes resources applied"
}

# =======================================
# Wait for Rollout
# =======================================

wait_for_rollout() {
    print_header "Waiting for Rollout"
    
    print_info "Waiting for deployment to be ready..."
    kubectl rollout status deployment/"$SERVICE_NAME" -n "$NAMESPACE" --timeout=5m
    
    print_success "Rollout completed"
}

# =======================================
# Get Service Information
# =======================================

get_service_info() {
    print_header "Service Information"
    
    echo -e "${GREEN}Deployment:${NC}"
    kubectl get deployment "$SERVICE_NAME" -n "$NAMESPACE"
    
    echo -e "\n${GREEN}Pods:${NC}"
    kubectl get pods -l app="$SERVICE_NAME" -n "$NAMESPACE"
    
    echo -e "\n${GREEN}Service:${NC}"
    kubectl get service "$SERVICE_NAME" -n "$NAMESPACE"
    
    # Get external IP with waiting logic
    local external_ip=$(wait_for_external_ip "$SERVICE_NAME" "$NAMESPACE")
    
    if [ -n "$external_ip" ]; then
        echo -e "\n${GREEN}✓ External IP: ${NC}$external_ip"
        echo -e "${GREEN}✓ Access your app at: ${NC}http://$external_ip"
        export EXTERNAL_IP="$external_ip"
    else
        print_warning "External IP not assigned within timeout. Run: kubectl get service $SERVICE_NAME -n $NAMESPACE"
    fi
}

# =======================================
# Print Summary
# =======================================

print_summary() {
    print_header "Deployment Complete!"
    
    echo -e "${GREEN}✓ Project: ${NC}$PROJECT_ID"
    echo -e "${GREEN}✓ Cluster: ${NC}$CLUSTER_NAME ($REGION)"
    echo -e "${GREEN}✓ Image: ${NC}$IMAGE_URL"
    echo -e "${GREEN}✓ Namespace: ${NC}$NAMESPACE"
    echo -e "${GREEN}✓ Service: ${NC}$SERVICE_NAME"
    
    if [ -n "$EXTERNAL_IP" ]; then
        echo -e "\n${YELLOW}Access URLs:${NC}"
        echo "  Main:     http://$EXTERNAL_IP"
        echo "  Health:   http://$EXTERNAL_IP/health"
        echo "  API Docs: http://$EXTERNAL_IP/docs"
        echo "  Info:     http://$EXTERNAL_IP/info"
    fi
    
    echo -e "\n${YELLOW}Useful Commands:${NC}"
    echo "  View pods:        kubectl get pods -n $NAMESPACE"
    echo "  View logs:        kubectl logs -l app=$SERVICE_NAME -n $NAMESPACE --tail=100"
    echo "  Scale:            kubectl scale deployment $SERVICE_NAME --replicas=3 -n $NAMESPACE"
    echo "  Delete:           kubectl delete deployment $SERVICE_NAME -n $NAMESPACE"
}

# =======================================
# Main Execution
# =======================================

main() {
    print_header "Application Deployment Pipeline"
    
    echo "Configuration:"
    echo "  Project:      $PROJECT_ID"
    echo "  Cluster:      $CLUSTER_NAME"
    echo "  Region:       $REGION"
    echo "  App:          $APP_NAME"
    echo "  Namespace:    $NAMESPACE"
    echo "  Registry:     $REGISTRY_TYPE"
    echo ""
    
    read -p "Continue with deployment? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Aborted by user"
        exit 0
    fi
    
    check_prerequisites
    gcloud config set project "$PROJECT_ID"
    configure_docker_auth
    build_image
    push_image
    get_cluster_credentials
    deploy_to_kubernetes
    wait_for_rollout
    get_service_info
    print_summary
}

# Run main function
main "$@"
