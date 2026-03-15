# Complete End-to-End ADK Deployment to Kubernetes

## 📋 Complete Deployment Guide for Google ADK Applications

This guide walks you through the entire process of deploying a Google Agents Development Kit (ADK) application to Google Kubernetes Engine (GKE), from initial development to production deployment.

---

## Table of Contents

1. [Development Phase](#1-development-phase)
2. [Containerization](#2-containerization)
3. [Kubernetes Configuration](#3-kubernetes-configuration)
4. [GCP Setup](#4-gcp-setup)
5. [Cluster Creation](#5-cluster-creation)
6. [Workload Identity](#6-workload-identity)
7. [Deployment](#7-deployment)
8. [Verification](#8-verification)
9. [Monitoring & Operations](#9-monitoring--operations)

---

## 1. Development Phase

### 1.1 Create ADK Application Structure

```bash
# Create project directory
mkdir my-adk-agent
cd my-adk-agent

# Create agent directory
mkdir agent-backend
cd agent-backend
```

### 1.2 Create agent.py

Create your ADK agent with proper configuration:

```python
# agent.py
from google.adk.agents import Agent
from google.adk.models import Model

# Define your agent
agent = Agent(
    name="my_agent",
    model=Model(
        model_id="gemini-2.5-flash",
        generation_config={
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 8192,
        }
    ),
    instructions="""You are a helpful AI assistant.
    Provide clear and concise responses to user queries.""",
    tools=[],  # Add your custom tools here
)
```

### 1.3 Create main.py

Create FastAPI server using ADK:

```python
# main.py
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google.adk.cli.fast_api import get_fast_api_app
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PORT = int(os.getenv("PORT", "8080"))
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_SERVICE_URI = "sqlite:///./sessions.db"

# CORS configuration
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "*"  # Remove in production
]

# Create ADK FastAPI app
try:
    app: FastAPI = get_fast_api_app(
        agents_dir=AGENT_DIR,
        session_service_uri=SESSION_SERVICE_URI,
        allow_origins=ALLOWED_ORIGINS,
        web=True,  # Enable web UI
        trace_to_cloud=True,  # Enable Cloud Trace
    )
    logger.info(f"Successfully initialized ADK app from {AGENT_DIR}")
except Exception as e:
    logger.error(f"Failed to initialize ADK app: {e}")
    raise

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "adk-agent",
        "version": "1.0"
    }

# Info endpoint
@app.get("/")
async def root():
    return {
        "service": "ADK Agent",
        "version": "1.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "web_ui": "/"
        }
    }

if __name__ == "__main__":
    import uvicorn
    
    print(f"\n{'='*60}")
    print(f"🤖 ADK Agent Server")
    print(f"{'='*60}")
    print(f"\n📍 Endpoints:")
    print(f"   Web UI:      http://localhost:{PORT}")
    print(f"   API Docs:    http://localhost:{PORT}/docs")
    print(f"   Health:      http://localhost:{PORT}/health")
    print(f"{'='*60}\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        ws_ping_interval=20,
        ws_ping_timeout=20,
        timeout_keep_alive=75,
    )
```

### 1.4 Create requirements.txt

```txt
# requirements.txt
# Google ADK
google-adk>=1.2.0

# Authentication
google-auth>=2.34.0
google-auth-httplib2>=0.2.0

# Google Cloud Services
google-cloud-aiplatform>=1.60.0

# HTTP Client
httpx>=0.27.0

# Web Server
fastapi>=0.115.0
uvicorn[standard]>=0.30.0

# Utilities
python-dotenv>=1.0.0
```

### 1.5 Create .env (for local development)

```bash
# .env
PORT=8080
PYTHONUNBUFFERED=1

# Add your API keys for local testing
# GOOGLE_MAPS_API_KEY=your-key-here
# CUSTOM_SEARCH_API_KEY=your-key-here
```

### 1.6 Test Locally

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run locally
python main.py

# Test in browser
open http://localhost:8080
```

---

## 2. Containerization

### 2.1 Create Dockerfile

```dockerfile
# Dockerfile
FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

# Use python -m to avoid exec format errors on multi-arch builds
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 2.2 Create .dockerignore

```
# .dockerignore
venv/
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
.env
.git
.gitignore
*.md
Dockerfile
.dockerignore
sessions.db
*.log
```

### 2.3 Test Docker Build Locally

```bash
# Build image (important: use linux/amd64 platform)
docker build --platform=linux/amd64 -t my-adk-agent:local .

# Run container locally
docker run -p 8080:8080 my-adk-agent:local

# Test in browser
open http://localhost:8080/health
```

---

## 3. Kubernetes Configuration

### 3.1 Create k8s/deployment.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: adk-agent
  labels:
    app: adk-agent
spec:
  replicas: 2
  selector:
    matchLabels:
      app: adk-agent
  template:
    metadata:
      labels:
        app: adk-agent
    spec:
      serviceAccountName: default  # Will be configured with Workload Identity
      containers:
      - name: adk-agent
        image: IMAGE_URL_PLACEHOLDER  # Will be replaced during deployment
        ports:
        - containerPort: 8080
          protocol: TCP
        env:
        - name: PORT
          value: "8080"
        - name: PYTHONUNBUFFERED
          value: "1"
        # Add your environment variables here
        # - name: GOOGLE_MAPS_API_KEY
        #   valueFrom:
        #     secretKeyRef:
        #       name: app-secrets
        #       key: GOOGLE_MAPS_API_KEY
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
```

### 3.2 Create k8s/service.yaml

```yaml
apiVersion: v1
kind: Service
metadata:
  name: adk-agent
  labels:
    app: adk-agent
spec:
  type: LoadBalancer
  selector:
    app: adk-agent
  ports:
  - name: http
    port: 80
    targetPort: 8080
    protocol: TCP
```

---

## 4. GCP Setup

### 4.1 Prerequisites

```bash
# Install Google Cloud SDK
# Visit: https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login
gcloud auth application-default login

# Create or select project
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Enable billing (required)
# Visit: https://console.cloud.google.com/billing
```

### 4.2 Enable Required APIs

```bash
# Enable all required APIs
gcloud services enable container.googleapis.com \
    compute.googleapis.com \
    aiplatform.googleapis.com \
    cloudresourcemanager.googleapis.com \
    iam.googleapis.com \
    logging.googleapis.com \
    monitoring.googleapis.com
```

### 4.3 Set Region

```bash
export REGION="europe-west4"
gcloud config set compute/region $REGION
```

---

## 5. Cluster Creation

### 5.1 Create GKE Autopilot Cluster

```bash
# Set cluster name
export CLUSTER_NAME="adk-agents-cluster"

# Create Autopilot cluster (5-10 minutes)
gcloud container clusters create-auto $CLUSTER_NAME \
    --region=$REGION \
    --project=$PROJECT_ID \
    --release-channel=regular \
    --enable-autoscaling \
    --enable-autorepair \
    --enable-stackdriver-kubernetes \
    --workload-pool="${PROJECT_ID}.svc.id.goog" \
    --logging=SYSTEM,WORKLOAD \
    --monitoring=SYSTEM
```

### 5.2 Get Cluster Credentials

```bash
# Configure kubectl
gcloud container clusters get-credentials $CLUSTER_NAME \
    --region=$REGION \
    --project=$PROJECT_ID

# Verify connection
kubectl get nodes
```

---

## 6. Workload Identity

### 6.1 Create Google Cloud Service Account

```bash
# Create service account
export SA_NAME="adk-agent-sa"
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create $SA_NAME \
    --display-name="ADK Agent Service Account" \
    --project=$PROJECT_ID
```

### 6.2 Grant Permissions

```bash
# Grant Vertex AI access (required for Gemini)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/aiplatform.user"

# Grant logging permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/logging.logWriter"

# Grant monitoring permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/monitoring.metricWriter"
```

### 6.3 Enable Workload Identity Binding

```bash
# Set Kubernetes service account
export K8S_NAMESPACE="default"
export K8S_SA="default"

# Bind GCP SA to K8s SA
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
    --role roles/iam.workloadIdentityUser \
    --member "serviceAccount:${PROJECT_ID}.svc.id.goog[${K8S_NAMESPACE}/${K8S_SA}]"

# Annotate Kubernetes service account
kubectl annotate serviceaccount $K8S_SA \
    -n $K8S_NAMESPACE \
    iam.gke.io/gcp-service-account=$SA_EMAIL \
    --overwrite
```

---

## 7. Deployment

### 7.1 Build and Push Docker Image

```bash
# Set image details
export IMAGE_NAME="adk-agent"
export IMAGE_TAG=$(date +%Y%m%d-%H%M%S)
export IMAGE_URL="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:${IMAGE_TAG}"

# Configure Docker for GCR
gcloud auth configure-docker

# Build image for linux/amd64 (GKE architecture)
docker build --platform=linux/amd64 -t $IMAGE_URL .

# Push to Google Container Registry
docker push $IMAGE_URL

# Also tag as latest
docker tag $IMAGE_URL gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest
docker push gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest
```

### 7.2 Deploy to Kubernetes

```bash
# Replace image placeholder in deployment
cat k8s/deployment.yaml | \
    sed "s|IMAGE_URL_PLACEHOLDER|$IMAGE_URL|g" | \
    kubectl apply -n $K8S_NAMESPACE -f -

# Apply service
kubectl apply -n $K8S_NAMESPACE -f k8s/service.yaml

# Wait for rollout
kubectl rollout status deployment/adk-agent -n $K8S_NAMESPACE
```

---

## 8. Verification

### 8.1 Check Deployment Status

```bash
# View deployment
kubectl get deployment adk-agent -n $K8S_NAMESPACE

# View pods
kubectl get pods -l app=adk-agent -n $K8S_NAMESPACE

# View service
kubectl get service adk-agent -n $K8S_NAMESPACE
```

### 8.2 Get External IP

```bash
# Get LoadBalancer IP (may take 2-5 minutes)
export EXTERNAL_IP=$(kubectl get service adk-agent -n $K8S_NAMESPACE \
    -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

echo "Application URL: http://$EXTERNAL_IP"
```

### 8.3 Test Endpoints

```bash
# Health check
curl http://$EXTERNAL_IP/health

# Access web UI
open http://$EXTERNAL_IP

# View API documentation
open http://$EXTERNAL_IP/docs
```

### 8.4 Check Logs

```bash
# View recent logs
kubectl logs -l app=adk-agent -n $K8S_NAMESPACE --tail=100

# Follow logs
kubectl logs -l app=adk-agent -n $K8S_NAMESPACE -f

# Check for errors
kubectl logs -l app=adk-agent -n $K8S_NAMESPACE | grep -i error
```

---

## 9. Monitoring & Operations

### 9.1 View Metrics

```bash
# Pod resource usage
kubectl top pods -l app=adk-agent -n $K8S_NAMESPACE

# Node resource usage
kubectl top nodes
```

### 9.2 Scale Deployment

```bash
# Scale to 3 replicas
kubectl scale deployment adk-agent --replicas=3 -n $K8S_NAMESPACE

# Verify scaling
kubectl get pods -l app=adk-agent -n $K8S_NAMESPACE
```

### 9.3 Update Deployment

```bash
# Build new image
export NEW_TAG=$(date +%Y%m%d-%H%M%S)
export NEW_IMAGE="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:${NEW_TAG}"

docker build --platform=linux/amd64 -t $NEW_IMAGE .
docker push $NEW_IMAGE

# Update deployment
kubectl set image deployment/adk-agent \
    adk-agent=$NEW_IMAGE \
    -n $K8S_NAMESPACE

# Monitor rollout
kubectl rollout status deployment/adk-agent -n $K8S_NAMESPACE
```

### 9.4 Rollback (if needed)

```bash
# Rollback to previous version
kubectl rollout undo deployment/adk-agent -n $K8S_NAMESPACE

# View rollout history
kubectl rollout history deployment/adk-agent -n $K8S_NAMESPACE
```

---

## 10. Managing Secrets

### 10.1 Create Kubernetes Secrets

```bash
# Create secret for API keys
kubectl create secret generic adk-secrets \
    --from-literal=GOOGLE_MAPS_API_KEY='your-key' \
    --from-literal=CUSTOM_SEARCH_KEY='your-key' \
    -n $K8S_NAMESPACE
```

### 10.2 Update Deployment to Use Secrets

Edit `k8s/deployment.yaml`:

```yaml
env:
- name: GOOGLE_MAPS_API_KEY
  valueFrom:
    secretKeyRef:
      name: adk-secrets
      key: GOOGLE_MAPS_API_KEY
- name: CUSTOM_SEARCH_KEY
  valueFrom:
    secretKeyRef:
      name: adk-secrets
      key: CUSTOM_SEARCH_KEY
```

Apply changes:

```bash
kubectl apply -f k8s/deployment.yaml -n $K8S_NAMESPACE
```

---

## 11. Cleanup

### 11.1 Delete Application

```bash
# Delete deployment and service
kubectl delete deployment adk-agent -n $K8S_NAMESPACE
kubectl delete service adk-agent -n $K8S_NAMESPACE
```

### 11.2 Delete Cluster

```bash
# Delete GKE cluster
gcloud container clusters delete $CLUSTER_NAME \
    --region=$REGION \
    --project=$PROJECT_ID
```

### 11.3 Delete Service Account

```bash
# Delete GCP service account
gcloud iam service-accounts delete $SA_EMAIL --project=$PROJECT_ID
```

---

## Common Issues & Solutions

### Issue 1: Permission Denied (403)

**Error:** `Permission 'aiplatform.endpoints.predict' denied`

**Solution:**

```bash
# Verify Workload Identity is configured
kubectl get sa default -n default -o yaml | grep gcp-service-account

# Re-grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/aiplatform.user"

# Restart pods
kubectl rollout restart deployment/adk-agent -n $K8S_NAMESPACE
```

### Issue 2: Pods Crashing - Exec Format Error

**Error:** `exec format error`

**Solution:**

```bash
# Ensure Dockerfile uses correct platform
# Dockerfile should have:
FROM --platform=linux/amd64 python:3.11-slim
CMD ["python", "-m", "uvicorn", "main:app", ...]

# Rebuild with platform flag
docker build --platform=linux/amd64 -t $IMAGE_URL .
docker push $IMAGE_URL
```

### Issue 3: LoadBalancer IP Pending

**Wait 2-5 minutes** for LoadBalancer provisioning.

Check status:

```bash
kubectl describe service adk-agent -n $K8S_NAMESPACE
```

---

## Best Practices

### Development

1. ✅ Test locally before containerizing
2. ✅ Use virtual environments
3. ✅ Keep requirements.txt updated
4. ✅ Implement proper logging

### Docker

1. ✅ Always specify `--platform=linux/amd64`
2. ✅ Use `.dockerignore` to reduce image size
3. ✅ Use `python -m uvicorn` instead of binary
4. ✅ Tag images with timestamps

### Kubernetes

1. ✅ Use Workload Identity (never use service account keys)
2. ✅ Set resource requests and limits
3. ✅ Implement health checks
4. ✅ Use secrets for sensitive data
5. ✅ Use Autopilot for managed infrastructure

### Security

1. ✅ Minimal IAM permissions
2. ✅ Never commit secrets to git
3. ✅ Use Workload Identity
4. ✅ Regular security updates

### Monitoring

1. ✅ Enable Cloud Logging
2. ✅ Enable Cloud Monitoring
3. ✅ Set up alerts
4. ✅ Monitor resource usage

---

## Quick Reference

### Essential Commands

```bash
# View pods
kubectl get pods -l app=adk-agent

# View logs
kubectl logs -l app=adk-agent --tail=100 -f

# Restart deployment
kubectl rollout restart deployment/adk-agent

# Scale deployment
kubectl scale deployment adk-agent --replicas=3

# Get external IP
kubectl get service adk-agent -o jsonpath='{.status.loadBalancer.ingress[0].ip}'

# Check pod details
kubectl describe pod POD_NAME

# Execute into pod
kubectl exec -it POD_NAME -- /bin/bash

# Port forward for debugging
kubectl port-forward POD_NAME 8080:8080
```

---

## Full Deployment Timeline

| Phase | Duration | Description |
|-------|----------|-------------|
| Development | 1-2 hours | Create ADK agent, test locally |
| Containerization | 30 min | Create Dockerfile, test container |
| K8s Configuration | 15 min | Create manifests |
| GCP Setup | 10 min | Enable APIs, configure |
| Cluster Creation | 5-10 min | Create GKE cluster |
| Workload Identity | 5 min | Configure authentication |
| Build & Push | 5-10 min | Build and push Docker image |
| Deployment | 3-5 min | Deploy to Kubernetes |
| Verification | 5 min | Test and verify |

**Total Time:** ~2-3 hours for first deployment, 10-15 minutes for updates

---

## Next Steps

1. **Set up CI/CD** - Automate deployments with Cloud Build or GitHub Actions
2. **Configure DNS** - Point custom domain to LoadBalancer IP
3. **Enable HTTPS** - Use Google-managed certificates
4. **Add monitoring** - Set up Cloud Monitoring alerts
5. **Implement caching** - Use Cloud CDN for performance
6. **Scale horizontally** - Increase replicas based on load
7. **Multi-environment** - Set up staging and production

---

**Congratulations!** 🎉 You now have a production-ready ADK application running on GKE!
