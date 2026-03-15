# Quick Start Guide - GKE Deployment

## 🚀 Get Running in 15 Minutes

This quick start guide will get your AI agent deployed to GKE Autopilot.

---

## Prerequisites (5 minutes)

### 1. Install Required Tools

```bash
# Check if tools are installed
gcloud --version
docker --version
kubectl version --client

# If missing, install:
# - gcloud: https://cloud.google.com/sdk/docs/install
# - Docker Desktop: https://www.docker.com/products/docker-desktop
# - kubectl: gcloud components install kubectl
```

### 2. Authenticate

```bash
# Login to Google Cloud
gcloud auth login

# Set application default credentials
gcloud auth application-default login

# Start Docker Desktop
open -a Docker  # macOS
# or start Docker Desktop from applications
```

---

## Deployment Steps

### Step 1: Configure (1 minute)

Edit `gke-deployment/config.env`:

```bash
cd gke-deployment

# Edit with your project ID
nano config.env
# Change: export GCP_PROJECT_ID="your-project-id"
# Save: Ctrl+O, Enter, Ctrl+X

# Load configuration
source config.env
```

### Step 2: Create Cluster (5-10 minutes)

```bash
cd scripts
./1-create-cluster.sh
```

**What this does:**

- Creates GKE Autopilot cluster in europe-west4
- Enables required APIs (GKE, Vertex AI, etc.)
- Configures Workload Identity
- Sets up logging and monitoring

**Expected time:** 5-10 minutes

☕ Grab a coffee while the cluster is being created!

### Step 3: Setup Authentication (2 minutes)

```bash
./2-setup-workload-identity.sh
```

**What this does:**

- Creates service account for your app
- Grants Vertex AI permissions
- Links Google and Kubernetes service accounts

**Expected time:** 1-2 minutes

### Step 4: Deploy Application (5 minutes)

```bash
./3-deploy-application.sh
```

**What this does:**

- Builds Docker image for linux/amd64
- Pushes to Google Container Registry
- Deploys to Kubernetes
- Creates LoadBalancer
- Waits for rollout

**Expected time:**

- First time: 5-7 minutes
- Subsequent: 2-3 minutes

---

## Access Your Application

### Get External IP

```bash
./utils.sh ip
```

Or:

```bash
kubectl get service bringo-multimodal-api
```

### Test Endpoints

```bash
# Set your external IP
EXTERNAL_IP="YOUR_IP_HERE"

# Health check
curl http://$EXTERNAL_IP/health

# API documentation
open http://$EXTERNAL_IP/docs

# Main interface
open http://$EXTERNAL_IP
```

---

## Verify Deployment

### Check Status

```bash
./utils.sh status
```

### View Logs

```bash
./utils.sh logs
```

### Expected Output

```
Deployment:
NAME               READY   UP-TO-DATE   AVAILABLE   AGE
bringo-multimodal-api   1/1     1            1           5m

Pods:
NAME                                READY   STATUS    RESTARTS   AGE
bringo-multimodal-api-67878554b4-hc68s   1/1     Running   0          5m

Service:
NAME               TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
bringo-multimodal-api   LoadBalancer   34.118.234.248  34.7.227.11   80:32499/TCP   5m

External IP:
34.7.227.11
```

✅ **Success!** Your application is running at `http://34.7.227.11`

---

## Common Commands

### View Application Logs

```bash
./utils.sh logs bringo-multimodal-api default 200
```

### Scale Application

```bash
./utils.sh scale bringo-multimodal-api 3
```

### Restart Application

```bash
./utils.sh restart
```

### Check Status

```bash
./utils.sh status
```

---

## What If Something Goes Wrong?

### Permission Errors

**Error:** `403 PERMISSION_DENIED`

**Fix:**

```bash
# Re-run Workload Identity setup
./2-setup-workload-identity.sh

# Restart application
./utils.sh restart
```

### Pods Not Starting

**Check logs:**

```bash
kubectl get pods
kubectl logs POD_NAME
```

**Common fix:**

```bash
# Ensure Docker is running
# Rebuild and redeploy
./3-deploy-application.sh
```

### External IP Pending

**Wait 5 minutes** - LoadBalancer takes time to provision.

Check again:

```bash
kubectl get service bringo-multimodal-api
```

---

## Next Steps

### Customize Your Deployment

1. **Change resources** - Edit `k8s/deployment.yaml`
2. **Add environment variables** - Use Kubernetes secrets
3. **Configure DNS** - Point domain to external IP
4. **Enable HTTPS** - Use Google-managed certificates

### Monitor Your Application

```bash
# View in GCP Console
echo "https://console.cloud.google.com/kubernetes/"

# Check logs
./utils.sh logs

# Monitor resources
kubectl top pods
```

### Update Your Application

```bash
# Make code changes
# Then redeploy
./3-deploy-application.sh
```

---

## Clean Up (Optional)

### Delete Application Only

```bash
./utils.sh delete
```

### Delete Everything (Cluster + Application)

```bash
# Delete cluster
gcloud container clusters delete ai-agents-cluster \
  --region=europe-west4 \
  --project=$GCP_PROJECT_ID

# Delete service account
gcloud iam service-accounts delete \
  bringo-multimodal-api-sa@$GCP_PROJECT_ID.iam.gserviceaccount.com
```

---

## Need Help?

- 📖 **Full documentation**: `README.md`
- 🔧 **Troubleshooting**: `docs/TROUBLESHOOTING.md`
- 💬 **GCP Support**: <https://cloud.google.com/support>

---

## Estimated Costs

### GKE Autopilot Pricing

- **Compute:** Pay only for pod resources
- **Typical cost:** $50-100/month for small app
- **First $300 free** with GCP trial

### Monitor Costs

```bash
# View billing in console
echo "https://console.cloud.google.com/billing/"

# Set budget alerts to avoid surprises
```

---

## Success Checklist

- [ ] Tools installed (gcloud, docker, kubectl)
- [ ] Authenticated to Google Cloud
- [ ] Cluster created successfully
- [ ] Workload Identity configured
- [ ] Application deployed
- [ ] External IP assigned
- [ ] Health check returns 200 OK
- [ ] Can access web interface

---

**🎉 Congratulations!** Your AI agent is now running on GKE!

**Next:** Explore the full [README.md](../README.md) for advanced configurations.
