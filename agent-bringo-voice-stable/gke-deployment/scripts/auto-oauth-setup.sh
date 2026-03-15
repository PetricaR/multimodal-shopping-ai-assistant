#!/bin/bash

# Attempts to automate the OAuth Client creation for IAP
# Note: Google is deprecating this CLI method. If it fails, use the Console.

PROJECT_ID="formare-ai"
SUPPORT_EMAIL="petrica.radan@formare.ai"
APPLICATION_TITLE="Bringo Multimodal API"

echo "Checking for existing IAP Brand..."
BRAND_NAME=$(gcloud alpha iap oauth-brands list --project=$PROJECT_ID --format="value(name)" | head -n 1)

if [ -z "$BRAND_NAME" ]; then
    echo "No brand found. Attempting to create one..."
    gcloud alpha iap oauth-brands create \
        --application_title="$APPLICATION_TITLE" \
        --support_email="$SUPPORT_EMAIL" \
        --project=$PROJECT_ID
    BRAND_NAME=$(gcloud alpha iap oauth-brands list --project=$PROJECT_ID --format="value(name)" | head -n 1)
fi

if [ -n "$BRAND_NAME" ]; then
    echo "Brand found: $BRAND_NAME"
    echo "Creating OAuth Client ID..."
    gcloud alpha iap oauth-clients create $BRAND_NAME \
        --display_name="IAP-Client-Generated" \
        --project=$PROJECT_ID
else
    echo "Failed to create or find a brand via CLI."
    echo "Google Cloud requires manual setup for safety: https://console.cloud.google.com/apis/credentials/consent?project=$PROJECT_ID"
fi
