# Infrastructure & Setup Guide

This document outlines the steps required to prepare the Google Cloud environment and set up the project for local development.

## ☁️ Google Cloud Requirements

Before running the API, ensure the following services are enabled and configured in your GCP project:

- **BigQuery**: Dataset containing a `products` table.
- **Vertex AI Vector Search**: An Index and Index Endpoint must be deployed.
- **Vertex AI Ranking API**: Enabled for high-precision reranking.
- **Service Account**: Must have the following roles:
  - Vertex AI User
  - BigQuery Job User
  - BigQuery Data Viewer
  - Storage Object Viewer

## 🔐 Configuration (Single Source of Truth)

We use a unified configuration file for both GKE deployments and the Python application. All settings are managed in `gke-deployment/config.env`.

### 1. Unified `config.env`

Ensure your `gke-deployment/config.env` contains these critical keys:

```bash
# Project Identification
export GCP_PROJECT_ID="your-project-id"
export AI_LOCATION="europe-west1"  # Vertex AI resources location

# Networking & Security
export LOADBALANCER_IP="34.78.177.35"         # Reserved Regional IP
export API_AUTH_KEY="your_secure_shield_key"  # Secret key for API Shield
export IAP_ENABLED="false"                    # Set to 'true' if using Domain + IAP

# BigQuery & Search
export BQ_DATASET="bringo_products_data"
export VS_ENDPOINT_NAME="bringo-product-endpoint-multimodal"
export VS_DEPLOYED_INDEX_ID="bringo_products_multimodal_deployed"
```

### 2. Streamlit Secrets (Frontend Auth)

To enable the Google Login flow in Streamlit, create a `.streamlit/secrets.toml` file:

```toml
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "random_string_for_cookies"
client_id = "your_google_oauth_client_id"
client_secret = "your_google_oauth_client_secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

## 💻 Local Development Setup

### 1. Python Environment

It is recommended to use a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Authentication

Log in to Google Cloud with the required scopes for BigQuery and Drive (if using federated tables):

```bash
gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive"
```

### 3. Running the API

Start the FastAPI server:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
```

### 4. Running the Frontend

In a separate terminal, launch the Streamlit demo:

```bash
streamlit run streamlit_app.py
```

## 📂 Product Data (Google Drive)

If your BigQuery tables are "Federated" (linked to Google Sheets/Drive), you **must** share the underlying Drive files with your Service Account email to avoid `403 Access Denied` errors.
