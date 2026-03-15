# Updating Your Agent Code

## 📝 Quick Answer

**To update your deployed agent after making code changes:**

```bash
# 1. Make your changes in agent-backend/
nano agent-backend/agent.py  # Edit your prompt or code

# 2. Deploy the update
cd gke-deployment/scripts
./3-deploy-application.sh

# That's it! Your changes are live in ~5 minutes
```

---

## Complete Update Workflow

### Step-by-Step Process

#### 1. Make Your Changes

Edit your agent code locally:

```bash
# Edit your agent prompt
nano agent-backend/agent.py

# Or edit main.py for server changes
nano agent-backend/main.py

# Or update dependencies
nano agent-backend/requirements.txt
```

**Example: Changing the agent prompt**

```python
# agent-backend/agent.py

agent = Agent(
    name="my_agent",
    model=Model(model_id="gemini-2.5-flash"),
    instructions="""
    NEW PROMPT HERE!
    You are now an expert in helping entrepreneurs.
    Provide detailed business advice.
    """,  # ← Your updated prompt
    tools=[],
)
```

#### 2. Test Locally (Optional but Recommended)

```bash
cd agent-backend

# Test your changes locally
python main.py

# Visit http://localhost:8080
# Verify your changes work
```

#### 3. Deploy to Cloud

```bash
cd ../gke-deployment/scripts

# This automatically:
# - Builds new Docker image with your changes
# - Pushes to Google Container Registry
# - Updates Kubernetes deployment
# - Does zero-downtime rolling update
./3-deploy-application.sh
```

#### 4. Verify Deployment

The script will:

- ✅ Build your updated code
- ✅ Push the new image
- ✅ Deploy to Kubernetes
- ✅ Wait for rollout to complete
- ✅ Show you the status

```bash
# After deployment, check it's working
export IP=$(kubectl get service bringo-multimodal-api -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
curl http://$IP/health

# Or visit in browser
open http://$IP
```

---

## What Happens During Deployment

### Behind the Scenes

1. **Build Phase** (~2-3 minutes)

   ```
   [INFO] Building Docker image
   → Copies your latest agent-backend/ code
   → Installs dependencies
   → Creates new image with timestamp tag
   ```

2. **Push Phase** (~1 minute)

   ```
   [INFO] Pushing to GCR
   → Uploads to gcr.io/formare-ai/bringo-multimodal-api:20251120-010500
   → Also tags as :latest
   ```

3. **Deploy Phase** (~2 minutes)

   ```
   [INFO] Deploying to Kubernetes
   → Updates deployment with new image
   → Starts new pods with updated code
   → Waits for new pods to be ready
   → Terminates old pods (zero downtime!)
   ```

### Rolling Update

Kubernetes does a **rolling update**:

- ✅ Starts new pods with your updated code
- ✅ Waits for them to be healthy
- ✅ Routes traffic to new pods
- ✅ Terminates old pods
- ✅ **Zero downtime** - users never see interruption

---

## Common Update Scenarios

### Update 1: Change Agent Prompt

```bash
# 1. Edit prompt
nano agent-backend/agent.py
# Update instructions="""..."""

# 2. Deploy
cd gke-deployment/scripts
./3-deploy-application.sh

# Done!
```

### Update 2: Add New Tool/Function

```bash
# 1. Edit agent.py
nano agent-backend/agent.py
# Add new tool to tools=[]

# 2. If new dependencies needed
nano agent-backend/requirements.txt
# Add new package

# 3. Deploy
cd gke-deployment/scripts
./3-deploy-application.sh
```

### Update 3: Change API Keys/Environment Variables

```bash
# 1. Update Kubernetes secret
kubectl create secret generic app-secrets \
  --from-literal=NEW_API_KEY='your-new-key' \
  --dry-run=client -o yaml | kubectl apply -f -

# 2. Restart pods to pick up new secret
kubectl rollout restart deployment bringo-multimodal-api

# No rebuild needed!
```

### Update 4: Change Resources (Memory/CPU)

```bash
# 1. Edit config
nano gke-deployment/config.env
# Change MEMORY_LIMIT or CPU_LIMIT

# 2. Regenerate YAML
cd gke-deployment/scripts
./0-generate-k8s-manifests.sh

# 3. Apply changes
kubectl apply -f ../k8s/deployment.yaml
```

---

## Quick Commands Reference

### Deploy Code Changes

```bash
cd gke-deployment/scripts
./3-deploy-application.sh
```

### Check Deployment Status

```bash
kubectl get pods
kubectl get deployment bringo-multimodal-api
```

### View Logs (See Your Updated Agent)

```bash
kubectl logs -l app=bringo-multimodal-api --tail=50 -f
```

### Rollback to Previous Version

```bash
kubectl rollout undo deployment bringo-multimodal-api
```

### Scale Up/Down

```bash
kubectl scale deployment bringo-multimodal-api --replicas=3
```

---

## Deployment Timeline

| What | Time | What Happens |
|------|------|--------------|
| **First deployment** | 5-7 min | Full build, push, deploy |
| **Code updates** | 2-3 min | Cached layers, fast build |
| **Just YAML changes** | <1 min | Apply config only |
| **Secret updates** | <1 min | Restart pods only |

---

## Pro Tips

### 1. Fast Iteration

For rapid development:

```bash
# Make changes, test locally first
cd agent-backend
python main.py  # Test at localhost:8080

# When ready, deploy
cd ../gke-deployment/scripts
./3-deploy-application.sh
```

### 2. Version Your Deployments

Images are automatically tagged with timestamps:

```
gcr.io/formare-ai/bringo-multimodal-api:20251120-010500
gcr.io/formare-ai/bringo-multimodal-api:20251120-011230
gcr.io/formare-ai/bringo-multimodal-api:latest
```

**To rollback to specific version:**

```bash
kubectl set image deployment/bringo-multimodal-api \
  bringo-multimodal-api=gcr.io/formare-ai/bringo-multimodal-api:20251120-010500
```

### 3. Watch Rollout Progress

```bash
# In one terminal
kubectl get pods -w

# In another terminal
cd gke-deployment/scripts
./3-deploy-application.sh

# Watch pods being replaced in real-time!
```

### 4. Quick Log Check

```bash
# After deployment, check logs immediately
kubectl logs -l app=bringo-multimodal-api --tail=20

# Look for your changes in action!
```

---

## Automated CI/CD (Future Enhancement)

For automatic deployments on git push:

```yaml
# .github/workflows/deploy.yml
name: Deploy to GKE

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy
        run: |
          cd gke-deployment/scripts
          ./3-deploy-application.sh
```

---

## Troubleshooting Updates

### New Pods Not Starting

```bash
# Check pod status
kubectl get pods

# View pod details
kubectl describe pod POD_NAME

# Check logs
kubectl logs POD_NAME
```

### Old Code Still Running

```bash
# Force rollout restart
kubectl rollout restart deployment bringo-multimodal-api

# Verify new image is used
kubectl get deployment bringo-multimodal-api -o yaml | grep image:
```

### Rollback Needed

```bash
# Rollback to previous version
kubectl rollout undo deployment bringo-multimodal-api

# Verify rollback
kubectl rollout status deployment bringo-multimodal-api
```

---

## Summary

### ✅ To Update Your Agent

1. **Edit code** in `agent-backend/`
2. **Run** `./3-deploy-application.sh`
3. **Wait** ~3-5 minutes
4. **Verify** changes are live

**That's it!** Your updated agent is deployed with zero downtime! 🚀

### Common Update Pattern

```bash
# Daily workflow
nano agent-backend/agent.py       # 1. Edit
python agent-backend/main.py      # 2. Test locally (optional)
cd gke-deployment/scripts          # 3. Navigate
./3-deploy-application.sh          # 4. Deploy
kubectl logs -l app=bringo-multimodal-api -f  # 5. Verify
```

**You can update as often as you want - the process is the same every time!**
