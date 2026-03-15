# Deployment Configuration

Organized deployment files for Bringo Chef AI services.

## Structure

```
deployment/
├── backend/
│   ├── deploy-backend-fast.sh      # Fast backend deployment script
│   ├── cloudbuild.backend.yaml     # Cloud Build config with Kaniko caching
│   └── Dockerfile.optimized        # Optimized multi-stage Dockerfile
├── frontend/
│   ├── deploy-frontend-fast.sh     # Fast frontend deployment script
│   ├── cloudbuild.frontend.yaml    # Cloud Build config with Kaniko caching
│   └── Dockerfile.optimized        # Optimized multi-stage Dockerfile
└── deploy-all-fast.sh              # Parallel deployment of both services
```

## Usage

### Deploy Both Services (Recommended)
```bash
cd deployment
./deploy-all-fast.sh
```

### Deploy Backend Only
```bash
cd deployment/backend
./deploy-backend-fast.sh
```

### Deploy Frontend Only
```bash
cd deployment/frontend
./deploy-frontend-fast.sh
```

## Performance

- **First deploy:** ~15-20 minutes (parallel)
- **Subsequent deploys:** ~2-5 minutes (with cache)
- **Speed improvement:** 6-10x faster than sequential builds

## Features

- ✅ Kaniko layer caching (7-day TTL)
- ✅ Parallel builds (backend + frontend simultaneously)
- ✅ Package caching (uv for Python, npm for Node)
- ✅ Multi-stage Docker builds
- ✅ High-CPU build machines (E2_HIGHCPU_8)
