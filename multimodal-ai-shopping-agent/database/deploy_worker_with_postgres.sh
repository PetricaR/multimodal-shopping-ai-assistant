#!/bin/bash
# Deploy Bringo Worker Pool with PostgreSQL Cloud SQL
# This redeploys the worker pool with Cloud SQL database connection

set -e

PROJECT_ID=${GCP_PROJECT_ID:-"formare-ai"}
REGION=${GCP_REGION:-"europe-west1"}
WORKER_POOL_NAME="bringo-session-keepalive"
INSTANCE_NAME="bringo-db"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Deploying Worker Pool with PostgreSQL${NC}"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Get database credentials from Secret Manager
echo -e "${YELLOW}🔐 Fetching database credentials...${NC}"

DB_USER=$(gcloud secrets versions access latest --secret="bringo-db-user" --project=$PROJECT_ID)
DB_PASSWORD=$(gcloud secrets versions access latest --secret="bringo-db-password" --project=$PROJECT_ID)
DB_NAME=$(gcloud secrets versions access latest --secret="bringo-db-name" --project=$PROJECT_ID)
CONNECTION_NAME=$(gcloud secrets versions access latest --secret="bringo-db-connection-name" --project=$PROJECT_ID)

echo -e "${GREEN}✅ Credentials retrieved${NC}"

# Rebuild Docker image with PostgreSQL support
echo -e "${YELLOW}📦 Rebuilding Docker image...${NC}"

gcloud builds submit \
  --config=workers/cloudbuild.yaml \
  --project=$PROJECT_ID

echo -e "${GREEN}✅ Image built${NC}"

# Deploy worker pool with Cloud SQL connection
echo -e "${YELLOW}🎯 Deploying worker pool...${NC}"

gcloud beta run worker-pools deploy $WORKER_POOL_NAME \
  --image=gcr.io/$PROJECT_ID/$WORKER_POOL_NAME:latest \
  --region=$REGION \
  --project=$PROJECT_ID \
  --cpu=1 \
  --memory=2Gi \
  --scaling=1 \
  --add-cloudsql-instances=$CONNECTION_NAME \
  --set-env-vars="
SESSION_REFRESH_BUFFER_MINUTES=60,
SESSION_POLL_INTERVAL_SECONDS=3600,
SESSION_VALIDATE_INTERVAL_MINUTES=15,
BRINGO_BASE_URL=https://www.bringo.ro,
BRINGO_STORE=carrefour_park_lake,
DB_HOST=/cloudsql/$CONNECTION_NAME,
DB_PORT=5432,
DB_NAME=$DB_NAME,
DB_USER=$DB_USER,
DB_PASSWORD=$DB_PASSWORD,
USE_POSTGRES=true
" \
  --update-labels="database=cloudsql"

echo -e "${GREEN}✅ Worker pool deployed with Cloud SQL!${NC}"
echo ""
echo "View logs:"
echo "  https://console.cloud.google.com/run/detail/$REGION/$WORKER_POOL_NAME/logs?project=$PROJECT_ID"
echo ""
echo "Check status:"
echo "  gcloud beta run worker-pools describe $WORKER_POOL_NAME --region=$REGION --project=$PROJECT_ID"
