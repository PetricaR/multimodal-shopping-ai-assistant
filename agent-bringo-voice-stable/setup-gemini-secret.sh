#!/bin/bash

# Script to set up Gemini API Key in Google Cloud Secret Manager
# Best practice: Store secrets in Secret Manager, not environment variables

set -e

PROJECT_ID="formare-ai"
SECRET_NAME="gemini-api-key"
REGION="europe-west1"

echo "🔐 Setting up Gemini API Key in Secret Manager"
echo "Project: $PROJECT_ID"
echo "Secret: $SECRET_NAME"
echo ""

# Check if user provided API key as argument
if [ -n "$1" ]; then
    API_KEY="$1"
    echo "✅ Using provided API key"
else
    # Prompt for API key
    echo "Please enter your Gemini API Key:"
    echo "(Get one from: https://aistudio.google.com/app/apikey)"
    read -s API_KEY
    echo ""
fi

if [ -z "$API_KEY" ]; then
    echo "❌ Error: No API key provided"
    exit 1
fi

# Check if secret already exists
if gcloud secrets describe $SECRET_NAME --project=$PROJECT_ID &>/dev/null; then
    echo "⚠️  Secret '$SECRET_NAME' already exists"
    echo "Adding new version..."
    echo -n "$API_KEY" | gcloud secrets versions add $SECRET_NAME \
        --data-file=- \
        --project=$PROJECT_ID
    echo "✅ Secret version added successfully"
else
    echo "Creating new secret..."
    echo -n "$API_KEY" | gcloud secrets create $SECRET_NAME \
        --data-file=- \
        --replication-policy="user-managed" \
        --locations=$REGION \
        --project=$PROJECT_ID
    echo "✅ Secret created successfully"
fi

# Get Cloud Run service account
SERVICE_ACCOUNT=$(gcloud run services describe bringo-api \
    --region=$REGION \
    --project=$PROJECT_ID \
    --format="value(spec.template.spec.serviceAccountName)" 2>/dev/null || echo "")

if [ -z "$SERVICE_ACCOUNT" ]; then
    # Use default compute service account
    PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
    SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
    echo "ℹ️  Using default service account: $SERVICE_ACCOUNT"
else
    echo "ℹ️  Using Cloud Run service account: $SERVICE_ACCOUNT"
fi

# Grant access to the secret
echo "Granting access to service account..."
gcloud secrets add-iam-policy-binding $SECRET_NAME \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID

echo ""
echo "✅ Setup complete!"
echo ""
echo "Secret details:"
echo "  Name: $SECRET_NAME"
echo "  Project: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Service Account: $SERVICE_ACCOUNT"
echo ""
echo "Next steps:"
echo "  1. Deploy backend: ./deploy-backend-cloudrun.sh"
echo "  2. Deploy frontend: ./deploy-frontend-cloudrun.sh"
