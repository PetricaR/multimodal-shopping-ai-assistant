# Complete GKE Deployment Guide

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Step-by-Step Guide](#step-by-step-guide)
5. [Configuration](#configuration)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)
8. [Complete End-to-End Guide](docs/END-TO-END-DEPLOYMENT.md) - Full ADK deployment process

---

## Overview

This guide provides complete automation for deploying AI agents to Google Kubernetes Engine (GKE) Autopilot clusters. It handles:

- ✅ GKE Autopilot cluster creation
- ✅ Workload Identity setup
- ✅ Service account configuration
- ✅ Docker image building and pushing
- ✅ Kubernetes deployment
- ✅ Load balancer configuration

### Why GKE Autopilot?

- **Fully Managed**: Google manages nodes, scaling, and upgrades
- **Cost Effective**: Pay only for pod resources
- **Secure by Default**: Automatic security hardening
- **Production Ready**: HA configuration out of the box

---

## Prerequisites

### Required Tools

Install these tools before starting:

```bash
# Google Cloud SDK
# Visit: https://cloud.google.com/sdk/docs/install

# Docker Desktop
# Visit: https://www.docker.com/products/docker-desktop

# kubectl (via gcloud)
gcloud components install kubectl

# gke-gcloud-auth-plugin
gcloud components install gke-gcloud-auth-plugin
```

### GCP Account Setup

1. **Create a GCP Project** (if you don't have one)
   - Visit [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable billing for the project

2. **Authenticate with gcloud**

   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

3. **Set your project ID**

   ```bash
   gcloud config set project YOUR_PROJECT_ID
   ```

---

## Quick Start

### 1. Configure Environment

Edit `config.env` with your settings:

```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="europe-west4"
export CLUSTER_NAME="ai-agents-cluster"
export APP_NAME="bringo-multimodal-api"
```

Load the configuration:

```bash
source config.env
```

### 2. Run All Scripts in Order

```bash
cd gke-deployment/scripts

# Step 1: Create GKE Autopilot Cluster (5-10 minutes)
chmod +x *.sh
./1-create-cluster.sh

# Step 2: Setup Workload Identity (2-3 minutes)
./2-setup-workload-identity.sh

# Step 3: Deploy Application (5-7 minutes)
./3-deploy-application.sh
```

### 3. Access Your Application

After deployment completes, get your external IP:

```bash
./utils.sh ip
```

Access your application:

- Main interface: `http://YOUR_EXTERNAL_IP`
- Health check: `http://YOUR_EXTERNAL_IP/health`
- API docs: `http://YOUR_EXTERNAL_IP/docs`

---

## Step-by-Step Guide

### Step 1: Create GKE Cluster

This script creates a production-ready GKE Autopilot cluster.

**What it does:**

- Enables required GCP APIs
- Creates regional Autopilot cluster
- Configures Workload Identity
- Sets up logging and monitoring

**Run:**

```bash
cd gke-deployment/scripts
./1-create-cluster.sh
```

**Configuration Options:**

You can override defaults with environment variables:

```bash
export GCP_PROJECT_ID="my-project"
export GCP_REGION="us-central1"
export CLUSTER_NAME="my-cluster"
./1-create-cluster.sh
```

**Expected Output:**

```
========================================
GKE Autopilot Cluster Creation Complete!
========================================

✓ GKE Autopilot Cluster: ai-agents-cluster
✓ Region: europe-west4
✓ Project: formare-ai
✓ Workload Identity: Enabled
```

---

### Step 2: Setup Workload Identity

Workload Identity allows Kubernetes pods to authenticate as GCP service accounts.

**What it does:**

- Creates GCP service account
- Grants Vertex AI permissions (for Gemini)
- Enables Workload Identity binding
- Annotates Kubernetes service account

**Run:**

```bash
./2-setup-workload-identity.sh
```

**Why Workload Identity?**

Without Workload Identity, your pods can't access GCP services like Vertex AI. This step is **critical** for AI agents using Gemini models.

**Permissions Granted:**

- `roles/aiplatform.user` - Access Vertex AI
- `roles/logging.logWriter` - Write logs
- `roles/monitoring.metricWriter` - Write metrics
- `roles/cloudtrace.agent` - Trace requests

---

### Step 3: Deploy Application

Builds Docker image and deploys to GKE.

**What it does:**

- Builds Docker image for linux/amd64 platform
- Pushes to Google Container Registry
- Applies Kubernetes deployment
- Creates LoadBalancer service
- Waits for rollout completion

**Run:**

```bash
./3-deploy-application.sh
```

**Build Details:**

- Platform: `linux/amd64` (required for GKE)
- Registry: Google Container Registry (GCR)
- Tags: timestamp + latest

**Expected Duration:**

- First build: 5-7 minutes
- Subsequent builds: 1-2 minutes (Docker layer caching)

---

## Configuration

### Environment Variables

All scripts use these environment variables (defined in `config.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `GCP_PROJECT_ID` | `formare-ai` | Your GCP project ID |
| `GCP_REGION` | `europe-west4` | GCP region for resources |
| `CLUSTER_NAME` | `ai-agents-cluster` | Name of GKE cluster |
| `APP_NAME` | `bringo-multimodal-api` | Application name |
| `K8S_NAMESPACE` | `default` | Kubernetes namespace |
| `REGISTRY_TYPE` | `gcr` | `gcr` or `artifact-registry` |

### Customizing Deployment

#### Change Number of Replicas

Edit `k8s/deployment.yaml`:

```yaml
spec:
  replicas: 3  # Change from 2 to 3
```

#### Change Resource Limits

Edit `k8s/deployment.yaml`:

```yaml
resources:
  requests:
    memory: "1Gi"    # Increase from 512Mi
    cpu: "1000m"     # Increase from 500m
  limits:
    memory: "2Gi"    # Increase from 1Gi
    cpu: "2000m"     # Increase from 1000m
```

#### Use Different Region

```bash
export GCP_REGION="us-central1"
```

---

## Utility Commands

The `utils.sh` script provides convenient commands:

### View Logs

```bash
./utils.sh logs                    # Last 100 lines
./utils.sh logs app-name default 200  # Last 200 lines
```

### Scale Deployment

```bash
./utils.sh scale bringo-multimodal-api 5  # Scale to 5 replicas
```

### Restart Deployment

```bash
./utils.sh restart  # Rolling restart
```

### Get External IP

```bash
./utils.sh ip
```

### Check Status

```bash
./utils.sh status
```

### Delete Deployment

```bash
./utils.sh delete  # WARNING: Deletes everything
```

---

## Troubleshooting

### Common Issues

#### 1. Permission Denied Error

**Error:**

```
403 PERMISSION_DENIED: Permission 'aiplatform.endpoints.predict' denied
```

**Solution:**

```bash
# Re-run the Workload Identity setup
./2-setup-workload-identity.sh

# Restart deployment
./utils.sh restart
```

#### 2. Pods in CrashLoopBackOff

**Check logs:**

```bash
kubectl get pods
kubectl logs POD_NAME
```

**Common causes:**

- Missing environment variables
- Wrong platform (must be linux/amd64)
- Service account issues

**Fix:**

```bash
# Rebuild with correct platform
./3-deploy-application.sh
```

#### 3. External IP Pending

**Check status:**

```bash
kubectl get service bringo-multimodal-api
```

**Wait:** LoadBalancer provisioning can take 2-5 minutes.

If still pending after 10 minutes:

```bash
kubectl describe service bringo-multimodal-api
```

#### 4. Docker Build Fails

**Error:** `exec format error`

**Cause:** Building for wrong architecture

**Fix:** Ensure Dockerfile has:

```dockerfile
FROM --platform=linux/amd64 python:3.11-slim
CMD ["python", "-m", "uvicorn", "main:app", ...]
```

---

## Best Practices

### Security

1. **Use Workload Identity** (not service account keys)
2. **Limit IAM permissions** to minimum required
3. **Use namespaces** for isolation
4. **Enable Binary Authorization** for image security

### Cost Optimization

1. **Right-size resources** - Don't over-provision
2. **Use Autopilot** - Pay only for pods
3. **Delete unused clusters**:

   ```bash
   gcloud container clusters delete CLUSTER_NAME --region=REGION
   ```

### Performance

1. **Use regional clusters** for HA
2. **Configure health checks** properly
3. **Set resource limits** to prevent overconsumption
4. **Use caching** in Docker builds

### Monitoring

1. **View logs regularly**:

   ```bash
   ./utils.sh logs bringo-multimodal-api default 500
   ```

2. **Check Cloud Console**:
   - [GKE Clusters](https://console.cloud.google.com/kubernetes/list)
   - [Cloud Logging](https://console.cloud.google.com/logs)
   - [Cloud Monitoring](https://console.cloud.google.com/monitoring)

3. **Set up alerts** for errors and resource usage

---

## Advanced Topics

### Using Artifact Registry Instead of GCR

1. Create repository:

   ```bash
   gcloud artifacts repositories create docker-repo \
     --repository-format=docker \
     --location=europe-west4
   ```

2. Update config:

   ```bash
   export REGISTRY_TYPE="artifact-registry"
   export AR_REPOSITORY="docker-repo"
   ```

3. Deploy as normal

### Multi-Environment Setup

Use different namespaces for environments:

```bash
# Production
export K8S_NAMESPACE="production"
./3-deploy-application.sh

# Staging
export APP_NAME="bringo-multimodal-api-staging"
export K8S_NAMESPACE="staging"
./3-deploy-application.sh
```

### Secrets Management

For API keys and secrets:

```bash
# Create secret
kubectl create secret generic app-secrets \
  --from-literal=API_KEY=your-key \
  --namespace=default

# Reference in deployment.yaml
env:
- name: API_KEY
  valueFrom:
    secretKeyRef:
      name: app-secrets
      key: API_KEY
```

---

## Scripts Reference

| Script | Purpose | Duration |
|--------|---------|----------|
| `1-create-cluster.sh` | Create GKE cluster | 5-10 min |
| `2-setup-workload-identity.sh` | Configure auth | 2-3 min |
| `3-deploy-application.sh` | Deploy app | 5-7 min |
| `utils.sh` | Management utilities | Instant |

---

## Support & Resources

- **GKE Documentation**: <https://cloud.google.com/kubernetes-engine/docs>
- **Workload Identity**: <https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity>
- **GKE Autopilot**: <https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview>
- **Vertex AI**: <https://cloud.google.com/vertex-ai/docs>

---

## Clean Up

To delete everything:

```bash
# Delete deployment
./utils.sh delete

# Delete cluster (WARNING: Irreversible!)
gcloud container clusters delete ai-agents-cluster \
  --region=europe-west4 \
  --project=formare-ai

# Delete service account
gcloud iam service-accounts delete \
  bringo-multimodal-api-sa@formare-ai.iam.gserviceaccount.com
```

---

**Last Updated:** November 2025  
**Version:** 1.0
