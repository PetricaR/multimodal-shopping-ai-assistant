#!/bin/bash

# Optimized Fast Deployment for Shopping AI Backend API
# Uses Cloud Build with Kaniko caching for 5-10x faster builds

set -e

# Configuration
PROJECT_ID="formare-ai"
REGION="europe-west1"
SERVICE_NAME="shopping-ai-api"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

# Cloud SQL Configuration
CLOUD_SQL_INSTANCE="formare-ai:europe-west1:bringo-db"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  🚀 Fast Deploy: Shopping AI Backend API                  ║"
echo "║  ⚡ Using Kaniko + Layer Caching                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Get database password from Secret Manager
echo "🔐 Fetching database credentials..."
DB_PASSWORD=$(gcloud secrets versions access latest --secret=bringo-db-password --project=${PROJECT_ID})
echo "✅ Credentials retrieved"
echo ""

# Build with Cloud Build + Kaniko caching
echo "📦 Building with Kaniko (cached layers)..."
echo "   This will be MUCH faster on subsequent builds!"
echo ""

gcloud builds submit \
  --config=deployment/backend/cloudbuild.backend.yaml \
  --project=${PROJECT_ID} \
  --substitutions=SHORT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "manual") \
  --timeout=20m \
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
  --port=8080 \
  --memory=4Gi \
  --cpu=2 \
  --timeout=300 \
  --max-instances=10 \
  --min-instances=1 \
  --concurrency=80 \
  --add-cloudsql-instances=${CLOUD_SQL_INSTANCE} \
  --set-secrets="GOOGLE_API_KEY=gemini-api-key:latest,GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY:latest" \
  --set-env-vars="USE_POSTGRES=true,DB_HOST=/cloudsql/${CLOUD_SQL_INSTANCE},DB_PORT=5432,DB_NAME=bringo_auth,DB_USER=bringo_user,DB_PASSWORD=${DB_PASSWORD},GCP_PROJECT_ID=${PROJECT_ID},PROJECT_ID=${PROJECT_ID},LOCATION=${REGION},BQ_DATASET=bringo_products_data,BQ_TABLE=bringo_products_native,BQ_OUTPUT_DATASET=bringo_similarity_search_multimodal,VS_INDEX_NAME=bringo-product-index-multimodal,VS_ENDPOINT_NAME=bringo-product-endpoint-multimodal,VS_DEPLOYED_INDEX_ID=bringo_products_multimodal_deployed,FS_PUBLIC_ENDPOINT=527765581332480.europe-west1-845266575866.featurestore.vertexai.goog,FS_METADATA_VIEW=bringo_product_data,ENABLE_SESSION_VALIDATION_ON_REQUEST=false,SESSION_REFRESH_BUFFER_MINUTES=30,BRINGO_BASE_URL=https://www.bringo.ro,BRINGO_USERNAME=radan.petrica@yahoo.com,BRINGO_PASSWORD=AgentAI2025,BRINGO_STORE=carrefour_park_lake,API_HOST=0.0.0.0,API_PORT=8080"

echo ""
echo "✅ Backend API deployed successfully!"
echo ""
echo "Service URL:"
gcloud run services describe ${SERVICE_NAME} \
  --platform=managed \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --format='value(status.url)'

echo ""
echo "📊 Performance Notes:"
echo "   • First build: ~15-20 minutes (downloading + caching)"
echo "   • Subsequent builds: ~2-5 minutes (using cache)"
echo "   • Cache TTL: 7 days"
echo ""
echo "View logs:"
echo "  https://console.cloud.google.com/run/detail/${REGION}/${SERVICE_NAME}/logs?project=${PROJECT_ID}"
echo ""
