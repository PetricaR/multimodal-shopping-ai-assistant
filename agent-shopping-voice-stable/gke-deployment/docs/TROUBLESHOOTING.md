# Troubleshooting Guide

## Common Issues & Solutions

### 1. Permission Errors

#### Error: `403 PERMISSION_DENIED aiplatform.endpoints.predict`

**Symptoms:**

```
google.genai.errors.ClientError: 403 PERMISSION_DENIED
Permission 'aiplatform.endpoints.predict' denied
```

**Cause:** Workload Identity not configured or service account lacks permissions.

**Solution:**

```bash
# Step 1: Verify Workload Identity is enabled on cluster
gcloud container clusters describe CLUSTER_NAME \
  --region=REGION \
  --format="value(workloadIdentityConfig.workloadPool)"

# Should output: PROJECT_ID.svc.id.goog

# Step 2: Re-run Workload Identity setup
cd gke-deployment/scripts
./2-setup-workload-identity.sh

# Step 3: Verify service account has permissions
gcloud projects get-iam-policy PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:bringo-multimodal-api-sa@PROJECT_ID.iam.gserviceaccount.com"

# Step 4: Restart pods
kubectl rollout restart deployment bringo-multimodal-api
```

---

### 2. Pods Crashing

#### Error: `CrashLoopBackOff`

**Check pod status:**

```bash
kubectl get pods -l app=bringo-multimodal-api
```

**View logs:**

```bash
kubectl logs POD_NAME --tail=100
```

**Common Causes & Solutions:**

#### A. Exec Format Error

**Error in logs:**

```
exec /usr/local/bin/uvicorn: exec format error
```

**Cause:** Docker image built for wrong architecture

**Solution:**

```bash
# Verify Dockerfile has --platform flag
cat agent-backend/Dockerfile | grep "FROM"
# Should show: FROM --platform=linux/amd64 python:3.11-slim

# Verify CMD uses python -m
cat agent-backend/Dockerfile | grep "CMD"
# Should show: CMD ["python", "-m", "uvicorn", ...]

# Rebuild
./3-deploy-application.sh
```

#### B. Missing Environment Variables

**Error in logs:**

```
KeyError: 'SOME_VARIABLE'
```

**Solution:**

Create Kubernetes secret:

```bash
kubectl create secret generic app-env \
  --from-literal=VARIABLE_NAME=value \
  --namespace=default
```

Update `k8s/deployment.yaml`:

```yaml
env:
- name: VARIABLE_NAME
  valueFrom:
    secretKeyRef:
      name: app-env
      key: VARIABLE_NAME
```

Redeploy:

```bash
kubectl apply -f k8s/deployment.yaml
```

#### C. Application Startup Failure

**Error in logs:**

```
Failed to initialize ADK FastAPI app
```

**Solution:**

1. Check if `agent.py` exists in application directory
2. Verify all dependencies are in `requirements.txt`
3. Check application logs for specific error
4. Test locally first:

   ```bash
   cd agent-backend
   python main.py
   ```

---

### 3. LoadBalancer Issues

#### External IP Shows `<pending>`

**Check status:**

```bash
kubectl get service bringo-multimodal-api
kubectl describe service bringo-multimodal-api
```

**Solutions:**

1. **Wait:** LoadBalancer provisioning takes 2-5 minutes

2. **Check Events:**

   ```bash
   kubectl describe service bringo-multimodal-api | grep Events -A 10
   ```

3. **Check Quotas:**

   ```bash
   gcloud compute project-info describe \
     --project=PROJECT_ID \
     --format="table(quotas[].metric,quotas[].limit,quotas[].usage)"
   ```

4. **If stuck after 10 minutes:**

   ```bash
   kubectl delete service bringo-multimodal-api
   kubectl apply -f k8s/service.yaml
   ```

---

### 4. Docker Build Failures

#### Error: Cannot connect to Docker daemon

**Error:**

```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock
```

**Solution:**

```bash
# Start Docker Desktop
open -a Docker

# Wait for Docker to start, then retry
./3-deploy-application.sh
```

#### Error: Platform mismatch warning

**Warning:**

```
FROM --platform flag should not use constant value
```

**This is expected** - we need constant value for Linux/amd64. Safe to ignore.

---

### 5. Image Push Failures

#### Error: `unauthorized: authentication required`

**Solution:**

```bash
# Re-authenticate Docker
gcloud auth configure-docker

# Or for Artifact Registry
gcloud auth configure-docker REGION-docker.pkg.dev

# Retry push
./3-deploy-application.sh
```

#### Error: `denied: Permission denied`

**Solution:**

```bash
# Grant permissions to push images
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="user:YOUR_EMAIL" \
  --role="roles/storage.admin"

# Retry
./3-deploy-application.sh
```

---

### 6. Cluster Creation Issues

#### Error: `Insufficient regional quota`

**Error:**

```
Quota 'CPUS' exceeded. Limit: 24.0 in region REGION
```

**Solutions:**

1. **Request quota increase:**
   - Visit: <https://console.cloud.google.com/iam-admin/quotas>
   - Filter: Compute Engine API
   - Select quota and click "Edit"

2. **Use different region:**

   ```bash
   export GCP_REGION="us-central1"
   ./1-create-cluster.sh
   ```

3. **Delete unused resources:**

   ```bash
   gcloud compute instances list
   gcloud compute disks list
   # Delete unused resources
   ```

#### Error: `API not enabled`

**Error:**

```
API [container.googleapis.com] not enabled on project
```

**Solution:**

```bash
gcloud services enable container.googleapis.com
gcloud services enable compute.googleapis.com
gcloud services enable aiplatform.googleapis.com

# Retry
./1-create-cluster.sh
```

---

### 7. Network/Connectivity Issues

#### Cannot access application via external IP

**Diagnostics:**

```bash
# Get external IP
EXTERNAL_IP=$(kubectl get service bringo-multimodal-api -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Test connectivity
curl -v http://$EXTERNAL_IP/health

# Check if pods are running
kubectl get pods -l app=bringo-multimodal-api

# Check pod logs
kubectl logs -l app=bringo-multimodal-api --tail=50
```

**Solutions:**

1. **Firewall rules:**

   ```bash
   # GKE Autopilot creates these automatically
   # But verify they exist:
   gcloud compute firewall-rules list --filter="name~gke"
   ```

2. **Health check failing:**

   ```bash
   # View pod logs for errors
   kubectl logs -l app=bringo-multimodal-api

   # Check health endpoint inside pod
   kubectl exec -it POD_NAME -- curl localhost:8080/health
   ```

3. **Service misconfiguration:**

   ```bash
   # Verify service selector matches pod labels
   kubectl get service bringo-multimodal-api -o yaml | grep selector -A 2
   kubectl get pods -l app=bringo-multimodal-api --show-labels
   ```

---

### 8. Workload Identity Issues

#### Pods cannot authenticate to GCP

**Verify setup:**

```bash
# Check pod has correct annotation
kubectl get pod POD_NAME -o yaml | grep "gcp-service-account"

# Should show: iam.gke.io/gcp-service-account: SA_EMAIL

# Check service account binding
gcloud iam service-accounts get-iam-policy SA_EMAIL

# Should include workloadIdentityUser binding
```

**Fix:**

```bash
# Re-run Workload Identity setup
./2-setup-workload-identity.sh

# Restart pods
kubectl rollout restart deployment bringo-multimodal-api
```

---

### 9. Deployment Timeout

#### Rollout exceeds progress deadline

**Error:**

```
error: deployment "bringo-multimodal-api" exceeded its progress deadline
```

**Causes:**

- Image pull issues
- Insufficient resources
- Health checks failing

**Diagnostics:**

```bash
# Check pod events
kubectl describe pod POD_NAME

# Check deployment events
kubectl describe deployment bringo-multimodal-api
```

**Solutions:**

1. **Image Pull Errors:**

   ```bash
   # Verify image exists
   gcloud container images list --repository=gcr.io/PROJECT_ID
   
   # Grant pull permissions
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:SA_EMAIL" \
     --role="roles/storage.objectViewer"
   ```

2. **Resource Issues:**

   ```bash
   # Check node resources
   kubectl top nodes
   
   # Reduce resource requests if needed
   # Edit k8s/deployment.yaml
   ```

3. **Health Check Issues:**

   ```bash
   # Increase initialDelaySeconds in deployment.yaml
   livenessProbe:
     initialDelaySeconds: 60  # Increase from 30
   ```

---

## Diagnostic Commands

### Quick Health Check

```bash
# All-in-one status check
./utils.sh status

# Or manually:
kubectl get all -n default
kubectl get pods -o wide
kubectl top pods
kubectl logs -l app=bringo-multimodal-api --tail=50
```

### Detailed Debugging

```bash
# View full pod description
kubectl describe pod POD_NAME

# Access pod shell
kubectl exec -it POD_NAME -- /bin/bash

# Port forward for local testing
kubectl port-forward POD_NAME 8080:8080
# Then visit http://localhost:8080

# View all events
kubectl get events --sort-by='.lastTimestamp'
```

### GCP Console Links

```bash
# Generate console URLs
PROJECT_ID="formare-ai"
REGION="europe-west4"
CLUSTER_NAME="ai-agents-cluster"

echo "GKE Console:"
echo "https://console.cloud.google.com/kubernetes/clusters/details/$REGION/$CLUSTER_NAME/details?project=$PROJECT_ID"

echo ""
echo "Cloud Logging:"
echo "https://console.cloud.google.com/logs/query?project=$PROJECT_ID"

echo ""
echo "Service Accounts:"
echo "https://console.cloud.google.com/iam-admin/serviceaccounts?project=$PROJECT_ID"
```

---

## Getting Help

### Enabling Debug Logs

Add to deployment.yaml:

```yaml
env:
- name: LOG_LEVEL
  value: "DEBUG"
```

### Collecting Diagnostic Info

```bash
# Create diagnostic report
kubectl get all -n default > diagnosis.txt
kubectl describe deployment bringo-multimodal-api >> diagnosis.txt
kubectl logs -l app=bringo-multimodal-api --tail=500 >> diagnosis.txt
kubectl get events --sort-by='.lastTimestamp' >> diagnosis.txt
```

### Support Channels

- GKE Issues: <https://cloud.google.com/support>
- Kubernetes: <https://kubernetes.io/docs/>
- Stack Overflow: Tag `google-kubernetes-engine`

---

## Prevention Best Practices

1. **Always test locally first**

   ```bash
   cd agent-backend
   docker build -t test-image .
   docker run -p 8080:8080 test-image
   ```

2. **Use staging environment**

   ```bash
   export K8S_NAMESPACE="staging"
   ./3-deploy-application.sh
   ```

3. **Monitor continuously**
   - Set up Cloud Monitoring alerts
   - Check logs regularly
   - Review resource usage

4. **Version your images**
   - Use semantic versioning
   - Keep old images for rollback
   - Tag releases

5. **Document changes**
   - Keep deployment notes
   - Track configuration changes
   - Maintain runbooks
