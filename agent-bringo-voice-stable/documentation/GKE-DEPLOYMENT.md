# GKE Deployment Guide

The Bringo Multimodal API is optimized for deployment on **Google Kubernetes Engine (GKE) Autopilot**. This provides a fully managed, secure, and production-ready environment.

## 📦 Deployment Package Structure

All deployment-related files are located in the `gke-deployment/` directory:

- `config.env`: Central configuration for project and cluster names.
- `scripts/`: Automated shell scripts for building and deploying.
- `k8s/`: Generated Kubernetes manifest files (YAML).

## 🚀 Production Deployment (Automated)

The easiest way to deploy the entire stack is using the master orchestration script:

```bash
# From the project root
bash deploy-all.sh
```

**What this script does:**

1. **Syncs Manifests**: Generates Kubernetes YAMLs based on your `config.env`.
2. **Hardens Security**: Configures Workload Identity (so Pods can access BigQuery/Vertex AI).
3. **Builds & Pushes**: Compiles the Docker image and pushes it to Google Container Registry.
4. **Rolls Out**: Updates the GKE cluster with the new image and networking rules.

---

## 🛠️ Manual Deployment Steps (For Testing)

If you need to run specific parts of the pipeline:

### 1. Workload Identity

```bash
cd gke-deployment/scripts
bash 2-setup-workload-identity.sh
```

### 2. Generate Manifests

```bash
bash 0-generate-k8s-manifests.sh
```

### 3. App Deployment

```bash
cd ../..
bash deploy-gke.sh
```

## 🔍 Management & Monitoring

### Get External IP

Once the deployment is finished, retrieve the LoadBalancer IP to access your API:

```bash
cd gke-deployment/scripts
./utils.sh ip
```

### Check Logs

Monitor the application logs for performance or errors:

```bash
./utils.sh logs
```

### Scale the App

GKE Autopilot scales automatically, but if you want to manually set a base replica count:

```bash
./utils.sh scale bringo-multimodal-api 5
```

## 🛠️ Security Best Practices (Shielded Architecture)

- **No JSON Keys**: We use **Workload Identity** exclusively. Pods inherit permissions directly from the Google Cloud metadata server.
- **API Shield**: The API is protected by a secret `X-API-KEY`. Even though the LoadBalancer IP is public, the application will reject any request that doesn't provide the valid key.
- **Frontend Auth**: The Streamlit application is protected by **Google OAuth 2.0**. Only users with authorized email addresses (e.g., `@formare.ai`) can access the search interface.
