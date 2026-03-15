#!/bin/bash

# Workload Identity Setup Script
# ================================
# This script configures Workload Identity for your GKE cluster
# allowing pods to authenticate as GCP service accounts

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
CLUSTER_NAME="${CLUSTER_NAME:-ai-agents-cluster}"
REGION="${GCP_REGION:-europe-west1}"

# Service Account Configuration
APP_NAME="${APP_NAME:-bringo-multimodal-api}"
GCP_SA_NAME="${APP_NAME}-sa"
K8S_NAMESPACE="${K8S_NAMESPACE:-default}"
K8S_SA_NAME="${K8S_SA_NAME:-${APP_NAME}-sa}"

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
# Create GCP Service Account
# =======================================

create_gcp_service_account() {
    print_header "Creating GCP Service Account"
    
    local sa_email="${GCP_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
    
    # Check if service account already exists
    if gcloud iam service-accounts describe "$sa_email" --project="$PROJECT_ID" &> /dev/null; then
        print_info "Service account $sa_email already exists. Continuing..."
    else
        print_info "Creating service account: $sa_email"
        gcloud iam service-accounts create "$GCP_SA_NAME" \
            --display-name="Service Account for $APP_NAME" \
            --project="$PROJECT_ID"
        
        print_info "Waiting for service account propagation..."
        sleep 10
        
        print_success "Service account created"
    fi
    
    export GCP_SA_EMAIL="$sa_email"
}

# =======================================
# Grant IAM Permissions
# =======================================

grant_iam_permissions() {
    print_header "Granting IAM Permissions"
    
    local roles=(
        "roles/aiplatform.user"              # Vertex AI access for Gemini
        "roles/logging.logWriter"            # Write logs
        "roles/monitoring.metricWriter"      # Write metrics
        "roles/cloudtrace.agent"            # Trace agent
        "roles/bigquery.jobUser"            # Run BQ jobs
        "roles/bigquery.dataViewer"         # View BQ data
        "roles/viewer"                      # Basic drive/project viewing
    )
    
    for role in "${roles[@]}"; do
        print_info "Granting $role to $GCP_SA_EMAIL"
        gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="serviceAccount:${GCP_SA_EMAIL}" \
            --role="$role" \
            --condition=None \
            > /dev/null
    done
    
    print_success "IAM permissions granted"
}

# =======================================
# Enable Workload Identity Binding
# =======================================

enable_workload_identity() {
    print_header "Enabling Workload Identity"
    
    print_info "Binding GCP SA to K8s SA..."
    print_info "  GCP SA: $GCP_SA_EMAIL"
    print_info "  K8s SA: $K8S_NAMESPACE/$K8S_SA_NAME"
    
    gcloud iam service-accounts add-iam-policy-binding "$GCP_SA_EMAIL" \
        --role roles/iam.workloadIdentityUser \
        --member "serviceAccount:${PROJECT_ID}.svc.id.goog[${K8S_NAMESPACE}/${K8S_SA_NAME}]" \
        --project="$PROJECT_ID"
    
    print_success "Workload Identity binding created"
}

# =======================================
# Annotate Kubernetes Service Account
# =======================================

annotate_k8s_service_account() {
    print_header "Configuring Kubernetes Service Account"
    
    # Get cluster credentials
    print_info "Getting cluster credentials..."
    gcloud container clusters get-credentials "$CLUSTER_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        > /dev/null
    
    # Check if namespace exists
    if ! kubectl get namespace "$K8S_NAMESPACE" &> /dev/null; then
        print_info "Creating namespace: $K8S_NAMESPACE"
        kubectl create namespace "$K8S_NAMESPACE"
    fi
    
    # Check if service account exists
    if ! kubectl get serviceaccount "$K8S_SA_NAME" -n "$K8S_NAMESPACE" &> /dev/null; then
        print_info "Creating Kubernetes service account: $K8S_SA_NAME"
        kubectl create serviceaccount "$K8S_SA_NAME" -n "$K8S_NAMESPACE"
    fi
    
    # Annotate the service account
    print_info "Annotating service account with Workload Identity..."
    kubectl annotate serviceaccount "$K8S_SA_NAME" \
        -n "$K8S_NAMESPACE" \
        iam.gke.io/gcp-service-account="$GCP_SA_EMAIL" \
        --overwrite
    
    print_success "Kubernetes service account configured"
}

# =======================================
# Verify Setup
# =======================================

verify_setup() {
    print_header "Verifying Setup"
    
    print_info "GCP Service Account:"
    gcloud iam service-accounts describe "$GCP_SA_EMAIL" \
        --project="$PROJECT_ID" \
        --format="table(email,displayName)"
    
    echo ""
    print_info "IAM Policy Bindings:"
    gcloud iam service-accounts get-iam-policy "$GCP_SA_EMAIL" \
        --project="$PROJECT_ID" \
        --format="table(bindings.role,bindings.members)"
    
    echo ""
    print_info "Kubernetes Service Account:"
    kubectl get serviceaccount "$K8S_SA_NAME" -n "$K8S_NAMESPACE" -o yaml | grep -A 2 "annotations:"
    
    print_success "Setup verified"
}

# =======================================
# Summary
# =======================================

print_summary() {
    print_header "Workload Identity Setup Complete!"
    
    echo -e "${GREEN}✓ GCP Service Account: ${NC}$GCP_SA_EMAIL"
    echo -e "${GREEN}✓ K8s Service Account: ${NC}$K8S_NAMESPACE/$K8S_SA_NAME"
    echo -e "${GREEN}✓ Workload Identity: ${NC}Enabled"
    echo -e "${GREEN}✓ Vertex AI Access: ${NC}Granted"
    
    echo -e "\n${YELLOW}Configuration Summary:${NC}"
    echo "  Project:         $PROJECT_ID"
    echo "  Cluster:         $CLUSTER_NAME"
    echo "  Region:          $REGION"
    echo "  GCP SA:          $GCP_SA_EMAIL"
    echo "  K8s Namespace:   $K8S_NAMESPACE"
    echo "  K8s SA:          $K8S_SA_NAME"
    
    echo -e "\n${YELLOW}Next Steps:${NC}"
    echo "1. Update your deployment YAML to use serviceAccountName: $K8S_SA_NAME"
    echo "2. Run: ${BLUE}./3-deploy-application.sh${NC}"
    
    echo -e "\n${YELLOW}Important Notes:${NC}"
    echo "• Pods using this SA can authenticate as: $GCP_SA_EMAIL"
    echo "• This SA has Vertex AI access for Gemini models"
    echo "• Workload Identity is the recommended way to authenticate on GKE"
}

# =======================================
# Main Execution
# =======================================

main() {
    print_header "Workload Identity Setup"
    
    echo "This script will:"
    echo "  1. Create a GCP service account"
    echo "  2. Grant necessary IAM permissions"
    echo "  3. Enable Workload Identity binding"
    echo "  4. Configure Kubernetes service account"
    echo ""
    echo "Configuration:"
    echo "  Project ID:      $PROJECT_ID"
    echo "  Cluster:         $CLUSTER_NAME"
    echo "  Region:          $REGION"
    echo "  App Name:        $APP_NAME"
    echo "  GCP SA Name:     $GCP_SA_NAME"
    echo "  K8s Namespace:   $K8S_NAMESPACE"
    echo "  K8s SA Name:     $K8S_SA_NAME"
    echo ""
    
    create_gcp_service_account
    grant_iam_permissions
    enable_workload_identity
    annotate_k8s_service_account
    verify_setup
    print_summary
}

# Run main function
main "$@"
