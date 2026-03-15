# Bringo Session Keep-Alive Worker Pool

Background worker that keeps Bringo authentication sessions alive by proactively refreshing them before expiration.

## Architecture

This worker implements the [Cloud Run Worker Pool](https://cloud.google.com/run/docs/deploy-worker-pools) pattern for continuous, non-HTTP background processing.

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    Worker Pool Pattern                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐                     │
│  │   Poll DB    │─────▶│ Check if     │                     │
│  │  for Sessions│      │ Refresh      │                     │
│  │   (60s)      │      │  Needed      │                     │
│  └──────────────┘      └──────┬───────┘                     │
│                               │                              │
│                        ┌──────▼────────┐                    │
│                        │  Needs        │                    │
│                        │  Refresh?     │                    │
│                        └──┬────────┬───┘                    │
│                           │        │                         │
│                    Yes ◀──┘        └──▶ No                  │
│                     │                   │                    │
│              ┌──────▼─────┐      ┌─────▼──────┐            │
│              │  Selenium  │      │   Sleep    │            │
│              │  Login     │      │   60s      │            │
│              │  (Bringo)  │      └────────────┘            │
│              └──────┬─────┘                                 │
│                     │                                        │
│              ┌──────▼─────┐                                 │
│              │  Update    │                                 │
│              │  Database  │                                 │
│              │  with New  │                                 │
│              │  Session   │                                 │
│              └────────────┘                                 │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Key Features

1. **Proactive Refresh**: Refreshes sessions BEFORE they expire (configurable buffer)
2. **Server Validation**: Periodically validates sessions with Bringo server
3. **Auto-Recovery**: Automatically re-authenticates if session expires
4. **Graceful Shutdown**: Handles SIGTERM/SIGINT for clean shutdown
5. **Low Overhead**: Minimal resource usage (1 CPU, 2GB RAM)

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_REFRESH_BUFFER_MINUTES` | 30 | Refresh session this many minutes before expiration |
| `SESSION_POLL_INTERVAL_SECONDS` | 60 | How often to check for sessions needing refresh |
| `SESSION_VALIDATE_INTERVAL_MINUTES` | 15 | How often to validate session with Bringo server |
| `BRINGO_USERNAME` | - | Bringo account email |
| `BRINGO_PASSWORD` | - | Bringo account password |
| `BRINGO_STORE` | carrefour_park_lake | Default store ID |

## Deployment Options

### Option 1: Google Cloud Run Worker Pool (Recommended for Production)

**Benefits:**
- ✅ Serverless, fully managed
- ✅ Auto-scaling (though we use min=max=1 for this use case)
- ✅ Built-in logging and monitoring
- ✅ No infrastructure management
- ✅ Cost-effective for continuous workloads

**Deploy:**

```bash
# Make script executable
chmod +x workers/deploy-worker-pool.sh

# Set environment variables
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
export GCP_SERVICE_ACCOUNT="your-service-account@project.iam.gserviceaccount.com"

# Deploy
./workers/deploy-worker-pool.sh
```

**View Logs:**

```bash
gcloud run worker-pools logs read bringo-session-keepalive \
    --region us-central1 \
    --project your-project-id \
    --follow
```

### Option 2: Docker Compose (Local Testing)

**Run locally:**

```bash
# Start worker
docker-compose -f workers/docker-compose.worker.yml up -d

# View logs
docker-compose -f workers/docker-compose.worker.yml logs -f

# Stop worker
docker-compose -f workers/docker-compose.worker.yml down
```

### Option 3: Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bringo-session-keepalive
spec:
  replicas: 1
  selector:
    matchLabels:
      app: bringo-session-keepalive
  template:
    metadata:
      labels:
        app: bringo-session-keepalive
    spec:
      containers:
      - name: worker
        image: gcr.io/your-project/bringo-session-keepalive:latest
        env:
        - name: SESSION_REFRESH_BUFFER_MINUTES
          value: "30"
        - name: SESSION_POLL_INTERVAL_SECONDS
          value: "60"
        - name: BRINGO_USERNAME
          valueFrom:
            secretKeyRef:
              name: bringo-credentials
              key: username
        - name: BRINGO_PASSWORD
          valueFrom:
            secretKeyRef:
              name: bringo-credentials
              key: password
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 1000m
            memory: 2Gi
```

### Option 4: Systemd Service (Linux Server)

```bash
# Create service file
sudo nano /etc/systemd/system/bringo-session-worker.service
```

```ini
[Unit]
Description=Bringo Session Keep-Alive Worker
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/agent-bringo
Environment="SESSION_REFRESH_BUFFER_MINUTES=30"
Environment="SESSION_POLL_INTERVAL_SECONDS=60"
Environment="BRINGO_USERNAME=your-email@example.com"
Environment="BRINGO_PASSWORD=your-password"
ExecStart=/usr/bin/python3 workers/session_keepalive_worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable bringo-session-worker
sudo systemctl start bringo-session-worker

# View logs
sudo journalctl -u bringo-session-worker -f
```

## Monitoring

### Log Messages

The worker produces structured logs:

```
✅ Session refreshed successfully! New expiration: 2026-02-01T18:30:00
⏰ Session expires in 25.3 minutes - triggering refresh
🔍 Last validation was 16.2 minutes ago - validating
⚠️ Session for user@example.com expired on server
✓ Session for user@example.com is healthy
```

### Metrics to Monitor

1. **Refresh Rate**: How often sessions are being refreshed
2. **Validation Failures**: Sessions failing server validation
3. **Error Rate**: Authentication failures
4. **Worker Health**: Ensure worker is running continuously

## Cost Analysis

### Cloud Run Worker Pool Pricing (Estimated)

- **CPU**: 1 vCPU @ $0.00002400/vCPU-second
- **Memory**: 2 GiB @ $0.00000250/GiB-second
- **Running 24/7**: ~$52/month

**Cost Breakdown:**
- CPU: 1 × $0.00002400 × 2,592,000 seconds/month = $62.21/month
- Memory: 2 × $0.00000250 × 2,592,000 seconds/month = $12.96/month
- **Total**: ~$75/month

**Note**: This is a continuous workload, so traditional Cloud Run Services would be more expensive. Worker Pools are optimized for this use case.

## Benefits Over Current Implementation

### Before (Reactive):
- ❌ Session expires during user requests
- ❌ Adds latency when re-authenticating
- ❌ Users experience interruptions
- ❌ Risk of rate-limiting from frequent re-auth

### After (Proactive with Worker Pool):
- ✅ Sessions always fresh
- ✅ Zero latency on user requests
- ✅ Seamless user experience
- ✅ Controlled, predictable authentication timing
- ✅ Better security (sessions don't linger expired)

## Troubleshooting

### Worker Not Starting

```bash
# Check logs
docker-compose -f workers/docker-compose.worker.yml logs

# Common issues:
# 1. Missing credentials in .env
# 2. Chrome/Selenium issues (check Chrome installation)
# 3. Database permissions
```

### Sessions Still Expiring

```bash
# Check worker is running
docker-compose -f workers/docker-compose.worker.yml ps

# Verify worker is actively refreshing
docker-compose -f workers/docker-compose.worker.yml logs -f | grep "Refreshing session"

# Reduce refresh buffer if needed
# Edit docker-compose.worker.yml:
# SESSION_REFRESH_BUFFER_MINUTES=45  # More aggressive
```

## Alternative: Simple Cron Job

If you don't need Cloud Run, you can use a simple cron job:

```bash
# Add to crontab (runs every 30 minutes)
*/30 * * * * cd /path/to/agent-bringo && python workers/session_keepalive_worker.py --once
```

Add `--once` flag support to the worker for single-run mode.

## References

- [Cloud Run Worker Pools Documentation](https://cloud.google.com/run/docs/deploy-worker-pools)
- [Exploring Cloud Run Worker Pools](https://cloud.google.com/blog/products/serverless/exploring-cloud-run-worker-pools-and-kafka-autoscaler)
- [Temporal Worker Pools on Cloud Run](https://gbostoen.medium.com/the-surprising-simplicity-of-temporal-worker-pools-on-cloud-run-b24b6bcc6308)
- [Background Sync Patterns](https://learn.microsoft.com/en-us/microsoft-edge/progressive-web-apps/how-to/background-syncs)
