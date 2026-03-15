#!/bin/bash

# GKE Autopilot Cluster Creation Script
# =======================================
# This script creates a production-ready GKE Autopilot cluster
# with all necessary configurations for running AI agents

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

# Project Configuration
PROJECT_ID="${GCP_PROJECT_ID:-formare-ai}"
REGION="${GCP_REGION:-europe-west1}"

# Cluster Configuration
CLUSTER_NAME="${CLUSTER_NAME:-ai-agents-cluster}"
CLUSTER_VERSION="${CLUSTER_VERSION:-1.33}"  # Autopilot auto-manages version
NETWORK="${NETWORK:-default}"

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

# =======================================
# Prerequisite Checks
# =======================================

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed. Please install it first."
        echo "Visit: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    
    print_info "gcloud CLI: ✓"
    
    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed. Please install it first."
        echo "Run: gcloud components install kubectl"
        exit 1
    fi
    
    print_info "kubectl: ✓"
    
    # Check if gke-gcloud-auth-plugin is installed
    if ! command -v gke-gcloud-auth-plugin &> /dev/null; then
        print_warning "gke-gcloud-auth-plugin not found. Installing..."
        gcloud components install gke-gcloud-auth-plugin --quiet
    fi
    
    print_info "gke-gcloud-auth-plugin: ✓"
    
    print_success "All prerequisites met!"
}

# =======================================
# Project Setup
# =======================================

setup_project() {
    print_header "Setting Up GCP Project"
    
    print_info "Project ID: $PROJECT_ID"
    print_info "Region: $REGION"
    
    # Set the project
    gcloud config set project "$PROJECT_ID"
    gcloud config set compute/region "$REGION"
    
    print_success "Project configured"
}

# =======================================
# Enable Required APIs
# =======================================

enable_apis() {
    print_header "Enabling Required APIs"
    
    local apis=(
        "container.googleapis.com"          # GKE
        "compute.googleapis.com"            # Compute Engine
        "aiplatform.googleapis.com"         # Vertex AI (for Gemini)
        "cloudresourcemanager.googleapis.com" # Resource Manager
        "iam.googleapis.com"                # IAM
        "logging.googleapis.com"            # Cloud Logging
        "monitoring.googleapis.com"         # Cloud Monitoring
    )
    
    for api in "${apis[@]}"; do
        print_info "Enabling $api..."
        gcloud services enable "$api" --project="$PROJECT_ID"
    done
    
    print_success "All APIs enabled"
}

# =======================================
# Create GKE Autopilot Cluster
# =======================================

create_cluster() {
    print_header "Creating GKE Autopilot Cluster"
    
    print_info "Cluster Name: $CLUSTER_NAME"
    print_info "Region: $REGION"
    print_info "Mode: Autopilot"
    
    # Check if cluster already exists
    if gcloud container clusters describe "$CLUSTER_NAME" --region="$REGION" --project="$PROJECT_ID" &> /dev/null; then
        print_warning "Cluster '$CLUSTER_NAME' already exists in region '$REGION'"
        read -p "Do you want to use the existing cluster? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Using existing cluster"
            return 0
        else
            print_error "Aborted. Please choose a different cluster name."
            exit 1
        fi
    fi
    
    print_info "Creating Autopilot cluster (this may take 5-10 minutes)..."
    
    # Autopilot clusters automatically manage autoscaling, autorepair, and other features
    # Many flags used in standard GKE are not needed or have different names in Autopilot
    gcloud container clusters create-auto "$CLUSTER_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --network="$NETWORK" \
        --release-channel="regular" \
        --logging=SYSTEM,WORKLOAD \
        --monitoring=SYSTEM
    
    print_success "Cluster created successfully!"
}

# =======================================
# Get Cluster Credentials
# =======================================

get_credentials() {
    print_header "Configuring kubectl Access"
    
    print_info "Fetching cluster credentials..."
    
    gcloud container clusters get-credentials "$CLUSTER_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID"
    
    print_info "Current context:"
    kubectl config current-context
    
    print_success "kubectl configured"
}

# =======================================
# Display Cluster Information
# =======================================

display_cluster_info() {
    print_header "Cluster Information"
    
    echo -e "${GREEN}Cluster Details:${NC}"
    gcloud container clusters describe "$CLUSTER_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="table(name,location,currentMasterVersion,status,currentNodeCount)"
    
    echo -e "\n${GREEN}Cluster Endpoints:${NC}"
    gcloud container clusters describe "$CLUSTER_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(endpoint)"
    
    echo -e "\n${GREEN}Nodes:${NC}"
    kubectl get nodes
}

# =======================================
# Summary
# =======================================

print_summary() {
    print_header "Cluster Creation Complete!"
    
    echo -e "${GREEN}✓ GKE Autopilot Cluster: ${NC}$CLUSTER_NAME"
    echo -e "${GREEN}✓ Region: ${NC}$REGION"
    echo -e "${GREEN}✓ Project: ${NC}$PROJECT_ID"
    echo -e "${GREEN}✓ Workload Identity: ${NC}Auto-configured"
    
    echo -e "\n${YELLOW}Next Steps:${NC}"
    echo "1. Run: ${BLUE}./2-setup-workload-identity.sh${NC}"
    echo "2. Then: ${BLUE}./3-deploy-application.sh${NC}"
    
    echo -e "\n${YELLOW}Cluster Access:${NC}"
    echo "  kubectl get nodes"
    echo "  kubectl get namespaces"
    
    echo -e "\n${YELLOW}View in Console:${NC}"
    echo "  https://console.cloud.google.com/kubernetes/clusters/details/$REGION/$CLUSTER_NAME/details?project=$PROJECT_ID"
}

# =======================================
# Main Execution
# =======================================

main() {
    print_header "GKE Autopilot Cluster Creation"
    
    echo "This script will:"
    echo "  1. Check prerequisites"
    echo "  2. Configure GCP project"
    echo "  3. Enable required APIs"
    echo "  4. Create GKE Autopilot cluster"
    echo "  5. Configure kubectl access"
    echo ""
    echo "Configuration:"
    echo "  Project ID:    $PROJECT_ID"
    echo "  Region:        $REGION"
    echo "  Cluster Name:  $CLUSTER_NAME"
    echo ""
    
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Aborted by user"
        exit 0
    fi
    
    check_prerequisites
    setup_project
    enable_apis
    create_cluster
    get_credentials
    display_cluster_info
    print_summary
}

# Run main function
main "$@"