#!/bin/bash
# Deploy Bringo Session Keep-Alive Worker to Google Cloud Run Worker Pool
# Reference: https://cloud.google.com/run/docs/deploy-worker-pools

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"your-project-id"}
REGION=${GCP_REGION:-"us-central1"}
WORKER_POOL_NAME="bringo-session-keepalive"
SERVICE_ACCOUNT=${GCP_SERVICE_ACCOUNT:-""}

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Deploying Bringo Session Keep-Alive Worker Pool${NC}"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Worker Pool: $WORKER_POOL_NAME"
echo ""

# Build and push container image
echo -e "${YELLOW}📦 Building container image...${NC}"
gcloud builds submit --tag gcr.io/$PROJECT_ID/$WORKER_POOL_NAME \
    --project $PROJECT_ID \
    --dockerfile workers/Dockerfile.worker

# Deploy worker pool
echo -e "${YELLOW}🎯 Deploying worker pool...${NC}"

DEPLOY_CMD="gcloud run worker-pools deploy $WORKER_POOL_NAME \
    --image gcr.io/$PROJECT_ID/$WORKER_POOL_NAME \
    --region $REGION \
    --project $PROJECT_ID \
    --cpu 1 \
    --memory 2Gi \
    --min-instances 1 \
    --max-instances 1"

# Add service account if specified
if [ -n "$SERVICE_ACCOUNT" ]; then
    DEPLOY_CMD="$DEPLOY_CMD --service-account $SERVICE_ACCOUNT"
fi

# Add environment variables
DEPLOY_CMD="$DEPLOY_CMD \
    --set-env-vars SESSION_REFRESH_BUFFER_MINUTES=30 \
    --set-env-vars SESSION_POLL_INTERVAL_SECONDS=60 \
    --set-env-vars SESSION_VALIDATE_INTERVAL_MINUTES=15"

eval $DEPLOY_CMD

echo -e "${GREEN}✅ Worker pool deployed successfully!${NC}"
echo ""
echo "To view logs:"
echo "  gcloud run worker-pools logs read $WORKER_POOL_NAME --region $REGION --project $PROJECT_ID"
echo ""
echo "To view details:"
echo "  gcloud run worker-pools describe $WORKER_POOL_NAME --region $REGION --project $PROJECT_ID"
echo ""
echo "To update environment variables:"
echo "  gcloud run worker-pools update $WORKER_POOL_NAME \\"
echo "    --region $REGION \\"
echo "    --project $PROJECT_ID \\"
echo "    --set-env-vars KEY=VALUE"
