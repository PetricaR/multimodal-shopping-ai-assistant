#!/bin/bash

# Optimized Fast Deployment for Shopping AI Frontend
# Uses Cloud Build with Kaniko caching for 5-10x faster builds

set -e

# Configuration
PROJECT_ID="formare-ai"
REGION="europe-west1"
SERVICE_NAME="shopping-ai-frontend"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  🚀 Fast Deploy: Shopping AI Frontend                     ║"
echo "║  ⚡ Using Kaniko + Layer Caching                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Get backend API URL if it exists
echo "🔍 Checking for backend API URL..."
BACKEND_URL=$(gcloud run services describe shopping-ai-api \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --format='value(status.url)' 2>/dev/null || echo "")

if [ -n "$BACKEND_URL" ]; then
  echo "✅ Backend API found: ${BACKEND_URL}"

  # Update frontend .env with backend URL
  echo "📝 Updating frontend environment..."
  cat > ./app/.env.production <<EOF
VITE_API_URL=${BACKEND_URL}
VITE_API_BASE_URL=${BACKEND_URL}/api/v1
EOF
  echo "✅ Environment configured"
else
  echo "⚠️  Backend API not found. Frontend will use default configuration."
  echo "   Deploy backend first with: ./deploy-backend-fast.sh"
fi

echo ""

# Build with Cloud Build + Kaniko caching
echo "📦 Building with Kaniko (cached layers)..."
echo "   This will be MUCH faster on subsequent builds!"
echo ""

gcloud builds submit \
  --config=deployment/frontend/cloudbuild.frontend.yaml \
  --project=${PROJECT_ID} \
  --substitutions=SHORT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "manual") \
  --timeout=15m \
  .

echo ""
echo "✅ Image built and pushed (with caching)"
echo ""

# Deploy to Cloud Run
echo "🎯 Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
  --image=${IMAGE_NAME} \
  --platform=managed \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --allow-unauthenticated \
  --port=80 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=60 \
  --max-instances=5 \
  --min-instances=0 \
  --concurrency=100

if [ -n "$BACKEND_URL" ]; then
  gcloud run services update ${SERVICE_NAME} \
    --region=${REGION} \
    --project=${PROJECT_ID} \
    --set-env-vars="VITE_API_URL=${BACKEND_URL},VITE_API_BASE_URL=${BACKEND_URL}/api/v1"
fi

echo ""
echo "✅ Frontend deployed successfully!"
echo ""
echo "Service URL:"
FRONTEND_URL=$(gcloud run services describe ${SERVICE_NAME} \
  --platform=managed \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --format='value(status.url)')

echo "${FRONTEND_URL}"
echo ""
echo "📊 Performance Notes:"
echo "   • First build: ~10-15 minutes (downloading + caching)"
echo "   • Subsequent builds: ~1-3 minutes (using cache)"
echo "   • Cache TTL: 7 days"
echo ""
echo "View logs:"
echo "  https://console.cloud.google.com/run/detail/${REGION}/${SERVICE_NAME}/logs?project=${PROJECT_ID}"
echo ""
echo "Open in browser:"
echo "  ${FRONTEND_URL}"
echo ""
