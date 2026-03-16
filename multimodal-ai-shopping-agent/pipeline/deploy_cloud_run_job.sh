#!/bin/bash
# ==============================================================================
# Bringo Full Pipeline - Cloud Run Job Deployment
# Project: formare-ai
# ==============================================================================
# 
# Uses local Docker to build and push, then creates/updates Cloud Run Job.
#
# Usage:
#   ./deploy_cloud_run_job.sh
#
# ==============================================================================

set -e

# Configuration
PROJECT_ID="formare-ai"
REGION="europe-west1"
JOB_NAME="bringo-parallel-scraper"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${JOB_NAME}"

echo "============================================================"
echo "BRINGO FULL PIPELINE - CLOUD RUN JOB DEPLOYMENT"
echo "============================================================"
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Job Name: ${JOB_NAME}"
echo ""
echo "Resources:"
echo "  Memory: 8 GB"
echo "  CPUs: 4"
echo "  Timeout: 4 hours"

echo "============================================================"

# Set project
echo ""
echo "Setting project to ${PROJECT_ID}..."
gcloud config set project ${PROJECT_ID}

# Configure Docker for GCR
echo ""
echo "Configuring Docker for Google Container Registry..."
gcloud auth configure-docker gcr.io --quiet

# Navigate to project root (parent of pipeline)
cd "$(dirname "$0")/.."
echo "Working directory: $(pwd)"

# Build Docker image locally (forcing linux/amd64 for Cloud Run compatibility)
echo ""
echo "Building Docker image locally (linux/amd64)..."
docker build --platform linux/amd64 -t ${IMAGE_NAME} -f pipeline/Dockerfile .

# Push to GCR
echo ""
echo "Pushing image to Google Container Registry..."
docker push ${IMAGE_NAME}

# Create or update Cloud Run Job
echo ""
echo "Creating/updating Cloud Run Job..."

# Try to create first, if already exists then update
if ! gcloud run jobs create ${JOB_NAME} \
    --image ${IMAGE_NAME} \
    --region ${REGION} \
    --memory 8Gi \
    --cpu 4 \
    --task-timeout 14400s \
    --max-retries 1 \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},BRINGO_STORE=carrefour_park_lake" 2>&1; then
    
    echo ""
    echo "Job already exists, updating..."
    gcloud run jobs update ${JOB_NAME} \
        --image ${IMAGE_NAME} \
        --region ${REGION} \
        --memory 8Gi \
        --cpu 4 \
        --task-timeout 14400s \
        --max-retries 1 \
        --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},BRINGO_STORE=carrefour_park_lake"
fi

echo ""
echo "============================================================"
echo "DEPLOYMENT COMPLETE"
echo "============================================================"
echo ""
echo "To execute the job manually:"
echo "  gcloud run jobs execute ${JOB_NAME} --region ${REGION}"
echo ""
echo "To view execution logs:"
echo "  gcloud run jobs executions list --job ${JOB_NAME} --region ${REGION}"
echo ""
echo "============================================================"

