# Automated YAML Generation

## Overview

The Kubernetes YAML files can be **automatically generated** from your configuration. You don't need to manually create or maintain them!

## Quick Start

```bash
cd gke-deployment/scripts

# Generate YAML files from config.env
./0-generate-k8s-manifests.sh
```

This creates:

- `gke-deployment/k8s/deployment.yaml`
- `gke-deployment/k8s/service.yaml`

## Configuration

Edit `gke-deployment/config.env` to customize your deployment:

```bash
# Application Configuration
export APP_NAME="bringo-multimodal-api"         # Name of your app
export K8S_NAMESPACE="default"             # Kubernetes namespace

# Resource Configuration
export REPLICAS="2"                        # Number of pod replicas
export PORT="8080"                         # Application port
export MEMORY_REQUEST="512Mi"              # Minimum memory
export MEMORY_LIMIT="1Gi"                  # Maximum memory
export CPU_REQUEST="500m"                  # Minimum CPU (0.5 cores)
export CPU_LIMIT="1000m"                   # Maximum CPU (1 core)
```

## Examples

### Example 1: Change App Name

```bash
# Edit config.env
export APP_NAME="my-custom-agent"

# Regenerate YAML
./0-generate-k8s-manifests.sh

# Result: All manifests will use "my-custom-agent"
```

### Example 2: Increase Resources

```bash
# Edit config.env
export REPLICAS="5"                    # Scale to 5 pods
export MEMORY_REQUEST="1Gi"            # More memory
export MEMORY_LIMIT="2Gi"
export CPU_REQUEST="1000m"             # 1 full CPU
export CPU_LIMIT="2000m"               # Up to 2 CPUs

# Regenerate YAML
./0-generate-k8s-manifests.sh
```

### Example 3: Different Namespace

```bash
# Edit config.env
export K8S_NAMESPACE="production"

# Regenerate YAML
./0-generate-k8s-manifests.sh

# Deploy to production namespace
kubectl create namespace production
./3-deploy-application.sh
```

## Complete Workflow

### Option 1: Fully Automated (Recommended)

```bash
# 1. Configure
cd gke-deployment
nano config.env  # Edit your settings

# 2. Generate YAML files
cd scripts
./0-generate-k8s-manifests.sh

# 3. Create cluster
./1-create-cluster.sh

# 4. Setup authentication
./2-setup-workload-identity.sh

# 5. Deploy application
./3-deploy-application.sh
```

### Option 2: Manual YAML (Advanced)

If you prefer manual control:

1. Skip `0-generate-k8s-manifests.sh`
2. Create `k8s/deployment.yaml` and `k8s/service.yaml` manually
3. Run deployment scripts as normal

## What Gets Generated

### deployment.yaml

Generated with:

- Configurable replicas
- Resource requests and limits
- Health checks (liveness and readiness probes)
- Environment variables
- Proper labels and selectors
- Workload Identity annotation

### service.yaml

Generated with:

- LoadBalancer type
- Port mapping (80 → your app port)
- Proper selectors
- Labels

## Customization After Generation

You can edit the generated YAML files for advanced customization:

```bash
# Generate base files
./0-generate-k8s-manifests.sh

# Then manually edit for advanced features
nano ../k8s/deployment.yaml

# Add custom environment variables, volumes, etc.
```

## When to Regenerate

Regenerate YAML files when you:

- Change app name
- Change resource requirements
- Change number of replicas
- Switch namespaces
- Want to reset to defaults

## Advanced: Environment Variables

To add custom environment variables, edit the generated `deployment.yaml`:

```yaml
env:
- name: PORT
  value: "8080"
- name: PYTHONUNBUFFERED
  value: "1"
# Add your custom variables:
- name: CUSTOM_VAR
  value: "custom-value"
# Or from secrets:
- name: API_KEY
  valueFrom:
    secretKeyRef:
      name: app-secrets
      key: API_KEY
```

## Benefits

✅ **No manual YAML writing** - Generated from config  
✅ **Consistent** - Always follows best practices  
✅ **Easy to update** - Change config, regenerate  
✅ **Version controlled** - Config.env is simple to track  
✅ **Error-free** - No YAML syntax mistakes  

## Alternative: kubectl create (Without YAML)

You can also deploy without YAML files:

```bash
# Create deployment directly
kubectl create deployment bringo-multimodal-api \
  --image=gcr.io/PROJECT/bringo-multimodal-api:latest

# Expose as LoadBalancer
kubectl expose deployment bringo-multimodal-api \
  --type=LoadBalancer \
  --port=80 \
  --target-port=8080
```

But using YAML files (especially auto-generated) is recommended for:

- Version control
- Reproducibility
- Advanced configuration
- Production deployments
