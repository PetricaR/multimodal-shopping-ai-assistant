# GKE Deployment - Complete Package

## 📁 Directory Structure

```
gke-deployment/
├── README.md                    # Complete deployment guide
├── QUICKSTART.md               # 15-minute quick start
├── INDEX.md                    # This file - package overview
├── config.env                  # Configuration file
│
├── scripts/                    # Deployment scripts
│   ├── 1-create-cluster.sh    # Create GKE Autopilot cluster
│   ├── 2-setup-workload-identity.sh  # Configure authentication
│   ├── 3-deploy-application.sh       # Deploy application
│   └── utils.sh               # Management utilities
│
├── k8s/                       # Kubernetes manifests
│   ├── deployment.yaml        # Application deployment
│   └── service.yaml           # LoadBalancer service
│
└── docs/                      # Additional documentation
    ├── END-TO-END-DEPLOYMENT.md   # Complete ADK deployment guide
    └── TROUBLESHOOTING.md         # Detailed troubleshooting guide
```

## 🎯 What's Included

### Scripts

1. **`1-create-cluster.sh`**
   - Creates production-ready GKE Autopilot cluster
   - Enables all required APIs
   - Configures Workload Identity
   - Sets up logging and monitoring
   - Duration: 5-10 minutes

2. **`2-setup-workload-identity.sh`**
   - Creates Google Cloud service account
   - Grants Vertex AI permissions  
   - Enables Workload Identity binding
   - Configures Kubernetes service account
   - Duration: 2-3 minutes

3. **`3-deploy-application.sh`**
   - Builds Docker image for linux/amd64
   - Pushes to Google Container Registry
   - Deploys to Kubernetes
   - Creates LoadBalancer service
   - Waits for rollout completion
   - Duration: 5-7 minutes (first time), 2-3 minutes (subsequent)

4. **`utils.sh`**
   - View logs
   - Scale deployment
   - Restart deployment
   - Get external IP
   - Check status
   - Delete deployment

### Configuration

**`config.env`**

- Centralized configuration
- Environment variables for all scripts
- Easy customization

### Documentation

1. **`README.md`** - Complete guide covering:
   - Prerequisites
   - Step-by-step instructions
   - Configuration options
   - Best practices
   - Advanced topics
   - Cost optimization
   - Security recommendations

2. **`QUICKSTART.md`** - Fast-track deployment:
   - Minimal steps to get running
   - Estimated times for each step
   - Quick troubleshooting
   - Success checklist

3. **`docs/TROUBLESHOOTING.md`** - Comprehensive troubleshooting:
   - Common errors and fixes
   - Diagnostic commands
   - Prevention best practices
   - Support resources

## 🚀 Usage

### First-Time Setup (Complete)

```bash
cd gke-deployment

# 1. Configure
source config.env
# Edit config.env with your project ID

# 2. Create cluster
cd scripts
./1-create-cluster.sh

# 3. Setup authentication
./2-setup-workload-identity.sh

# 4. Deploy application
./3-deploy-application.sh

# 5. Get your app's URL
./utils.sh ip
```

### Quick Deployment (Existing Cluster)

```bash
cd gke-deployment/scripts

# Just deploy
source ../config.env
./3-deploy-application.sh
```

### Daily Operations

```bash
cd gke-deployment/scripts

# View logs
./utils.sh logs

# Check status
./utils.sh status

# Scale to 3 replicas
./utils.sh scale bringo-multimodal-api 3

# Restart
./utils.sh restart

# Get external IP
./utils.sh ip
```

## 🎓 Learning Path

### Beginner

1. Start with **QUICKSTART.md**
2. Follow step-by-step
3. Don't customize yet
4. Get it working first

### Intermediate

1. Read **README.md** fully
2. Customize `config.env`
3. Modify resource limits
4. Add environment variables
5. Explore utils.sh commands

### Advanced

1. Study **TROUBLESHOOTING.md**
2. Implement multi-environment setup
3. Configure custom service accounts
4. Set up CI/CD pipeline
5. Enable monitoring and alerts

## ✅ Features

### Automation

- ✅ Complete cluster creation
- ✅ Automated authentication setup
- ✅ One-command deployment
- ✅ Utility scripts for management

### Production-Ready

- ✅ GKE Autopilot (fully managed)
- ✅ Workload Identity (secure auth)
- ✅ Regional deployment (HA)
- ✅ LoadBalancer (auto-scaling)
- ✅ Health checks
- ✅ Resource limits
- ✅ Logging and monitoring

### Well-Documented

- ✅ Step-by-step guides
- ✅ Troubleshooting documentation
- ✅ Inline script comments
- ✅ Usage examples
- ✅ Best practices

### Learnings Incorporated

- ✅ Correct platform (linux/amd64)
- ✅ Regional cluster configuration
- ✅ Workload Identity (not default SA)
- ✅ Vertex AI permissions
- ✅ Python -m uvicorn (not binary)
- ✅ Proper health check endpoints

## 🔧 Customization

### Change Region

```bash
export GCP_REGION="us-central1"
./1-create-cluster.sh
```

### Different App Name

```bash
export APP_NAME="my-custom-app"
./2-setup-workload-identity.sh
./3-deploy-application.sh
```

### Multiple Environments

```bash
# Production
export K8S_NAMESPACE="production"
export APP_NAME="app-prod"
./3-deploy-application.sh

# Staging
export K8S_NAMESPACE="staging"
export APP_NAME="app-staging"
./3-deploy-application.sh
```

## 📊 What You'll Get

After running all scripts successfully:

- **GKE Autopilot Cluster** in europe-west4
- **Service Account** with Vertex AI access
- **Workload Identity** configured
- **Deployed Application** with 1-2 replicas
- **LoadBalancer** with external IP
- **Health Checks** enabled
- **Logging** to Cloud Logging
- **Monitoring** in Cloud Monitoring

### Access Points

- `http://EXTERNAL_IP` - Main application
- `http://EXTERNAL_IP/health` - Health check
- `http://EXTERNAL_IP/docs` - API documentation
- `http://EXTERNAL_IP/info` - Agent information

## 🛡️ Security

All scripts implement security best practices:

- ✅ Workload Identity (no service account keys)
- ✅ Minimal IAM permissions
- ✅ Regional isolation
- ✅ Automatic security patches (Autopilot)
- ✅ Network policies (Autopilot default)

## 💰 Cost Estimate

### Typical Monthly Costs

- **GKE Autopilot**: $50-100/month
  - Pay only for pod resources
  - No cluster management fee for Autopilot
  
- **LoadBalancer**: ~$18/month
  - Forwarding rule: $0.025/hour
  
- **Egress**: Variable
  - First 1GB free
  - Then $0.12/GB

**Total:** ~$70-120/month for small app

### Cost Optimization

1. Use Autopilot (not Standard)
2. Right-size resource requests
3. Delete unused clusters
4. Use Cloud CDN for static assets
5. Monitor with budget alerts

## 🎯 Next Steps

### After Deployment

1. ✅ **Test your application**

   ```bash
   curl http://$(./utils.sh ip)/health
   ```

2. ✅ **Configure monitoring**
   - Set up alerts in Cloud Monitoring
   - Create uptime checks

3. ✅ **Add CI/CD**
   - Cloud Build integration
   - GitHub Actions
   - GitLab CI

4. ✅ **Custom domain**
   - Point DNS to external IP
   - Configure managed certificate

5. ✅ **Scale as needed**

   ```bash
   ./utils.sh scale app-name 5
   ```

## 📚 Documentation Links

- [Full Guide](README.md) - Complete documentation
- [Quick Start](QUICKSTART.md) - Get running in 15 min
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Fix common issues

## 🤝 Support

### Resources

- GKE Documentation: <https://cloud.google.com/kubernetes-engine/docs>
- Workload Identity: <https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity>
- Vertex AI: <https://cloud.google.com/vertex-ai/docs>

### Getting Help

1. Check **TROUBLESHOOTING.md** first
2. Review script output carefully
3. Use diagnostic commands
4. Contact GCP Support if needed

## 📝 Notes

### Important Reminders

- **Enable billing** on your GCP project
- **Authenticate** before running scripts
- **Start Docker Desktop** before deploying
- **Wait for LoadBalancer** (takes 2-5 min)
- **Check logs** if something fails

### Scripts are Idempotent

You can safely re-run scripts:

- Existing resources won't be duplicated
- Scripts check for existing resources
- Safe to retry after failures

## 🎉 Success Metrics

You'll know it's working when:

- ✅ All scripts complete without errors
- ✅ `kubectl get pods` shows Running
- ✅ `kubectl get service` shows external IP
- ✅ Health check returns 200 OK
- ✅ Can access web interface

---

**Version:** 1.0  
**Last Updated:** November 2025  
**Tested With:** GKE 1.33+, Google ADK 1.2+
