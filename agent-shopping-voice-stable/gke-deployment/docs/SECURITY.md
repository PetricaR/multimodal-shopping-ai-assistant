# Security Guide - Restrict Access to Specific Email Addresses

## Overview

Your deployed application is currently **publicly accessible** via the LoadBalancer IP. This guide shows you how to restrict access to specific email addresses.

---

## Table of Contents

1. [Identity-Aware Proxy (IAP)](#1-identity-aware-proxy-iap) - **Recommended**
2. [Application-Level Authentication](#2-application-level-authentication)
3. [Network-Level Security](#3-network-level-security)
4. [Comparison](#4-comparison)

---

## 1. Identity-Aware Proxy (IAP) ⭐ Recommended

**Best for:** Restricting access to specific Google accounts (email addresses)

### What is IAP?

Identity-Aware Proxy (IAP) is Google's managed service that controls access to your application based on user identity. It:

- ✅ Handles authentication automatically
- ✅ Works with Google accounts
- ✅ No code changes needed
- ✅ Centralized access control

### Setup IAP

#### Step 1: Configure OAuth Consent Screen

```bash
# Set your project
export PROJECT_ID="formare-ai"

# Enable IAP API
gcloud services enable iap.googleapis.com --project=$PROJECT_ID

# Create OAuth consent screen (do this in console first)
# Visit: https://console.cloud.google.com/apis/credentials/consent
```

**In the Console:**

1. Go to APIs & Services → OAuth consent screen
2. Choose "Internal" (for Google Workspace) or "External"
3. Fill in:
   - App name: "Bringo Multimodal API"
   - User support email: <your-email@formare.ai>
   - Developer contact: <your-email@formare.ai>
4. Save

#### Step 2: Switch from LoadBalancer to Ingress

IAP requires using an Ingress instead of LoadBalancer.

**Delete existing service:**

```bash
kubectl delete service bringo-multimodal-api
```

**Create Backend Config:**

```yaml
# k8s/backend-config.yaml
apiVersion: cloud.google.com/v1
kind: BackendConfig
metadata:
  name: bringo-multimodal-api-backend-config
spec:
  iap:
    enabled: true
    oauthclientCredentials:
      secretName: oauth-client-credentials
```

**Create new Service (ClusterIP):**

```yaml
# k8s/service-iap.yaml
apiVersion: v1
kind: Service
metadata:
  name: bringo-multimodal-api
  annotations:
    cloud.google.com/backend-config: '{"default": "bringo-multimodal-api-backend-config"}'
spec:
  type: ClusterIP  # Changed from LoadBalancer
  selector:
    app: bringo-multimodal-api
  ports:
  - name: http
    port: 80
    targetPort: 8080
```

**Create Ingress:**

```yaml
# k8s/ingress-iap.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: bringo-multimodal-api-ingress
  annotations:
    kubernetes.io/ingress.class: "gce"
    kubernetes.io/ingress.global-static-ip-name: "bringo-multimodal-api-ip"
spec:
  defaultBackend:
    service:
      name: bringo-multimodal-api
      port:
        number: 80
```

#### Step 3: Create OAuth Credentials

```bash
# Create OAuth client
# Visit: https://console.cloud.google.com/apis/credentials

# Note the Client ID and Client Secret
export CLIENT_ID="your-client-id.apps.googleusercontent.com"
export CLIENT_SECRET="your-client-secret"

# Create Kubernetes secret
kubectl create secret generic oauth-client-credentials \
  --from-literal=client_id=$CLIENT_ID \
  --from-literal=client_secret=$CLIENT_SECRET
```

#### Step 4: Apply Resources

```bash
kubectl apply -f k8s/backend-config.yaml
kubectl apply -f k8s/service-iap.yaml
kubectl apply -f k8s/ingress-iap.yaml
```

#### Step 5: Configure IAP Access

```bash
# Get the IAP service name
IAP_SERVICE=$(gcloud compute backend-services list --format="value(name)" --filter="name~bringo-multimodal-api")

# Grant access to specific email
gcloud iap web add-iam-policy-binding \
  --resource-type=backend-services \
  --service=$IAP_SERVICE \
  --member="user:petrica.radan@formare.ai" \
  --role="roles/iap.httpsResourceAccessor"

# Add more users
gcloud iap web add-iam-policy-binding \
  --resource-type=backend-services \
  --service=$IAP_SERVICE \
  --member="user:another.user@formare.ai" \
  --role="roles/iap.httpsResourceAccessor"
```

#### Step 6: Test

```bash
# Get Ingress IP (takes 5-10 minutes to provision)
kubectl get ingress bringo-multimodal-api-ingress

# Visit the IP in your browser
# You'll be prompted to sign in with Google
# Only authorized emails can access!
```

### Manage Access

```bash
# List current users
gcloud iap web get-iam-policy \
  --resource-type=backend-services \
  --service=$IAP_SERVICE

# Remove a user
gcloud iap web remove-iam-policy-binding \
  --resource-type=backend-services \
  --service=$IAP_SERVICE \
  --member="user:user@example.com" \
  --role="roles/iap.httpsResourceAccessor"

# Grant access to a group
gcloud iap web add-iam-policy-binding \
  --resource-type=backend-services \
  --service=$IAP_SERVICE \
  --member="group:team@formare.ai" \
  --role="roles/iap.httpsResourceAccessor"
```

---

## 2. Application-Level Authentication

**Best for:** Custom authentication logic, non-Google accounts

### Option A: OAuth2 with FastAPI

Add authentication to your FastAPI application:

```python
# In main.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from google.oauth2 import id_token
from google.auth.transport import requests

ALLOWED_EMAILS = [
    "petrica.radan@formare.ai",
    "another.user@formare.ai"
]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        idinfo = id_token.verify_oauth2_token(
            token, requests.Request(), 
            "YOUR_CLIENT_ID.apps.googleusercontent.com"
        )
        
        email = idinfo.get('email')
        if email not in ALLOWED_EMAILS:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        return idinfo
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

# Protect your endpoints
@app.get("/")
async def root(user = Depends(verify_token)):
    return {"message": f"Welcome {user['email']}"}
```

### Option B: API Key Authentication

Simple API key approach:

```python
# In main.py
from fastapi import Header, HTTPException

VALID_API_KEYS = {
    "key-for-user1": "petrica.radan@formare.ai",
    "key-for-user2": "another.user@formare.ai"
}

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return VALID_API_KEYS[x_api_key]

@app.get("/")
async def root(user_email = Depends(verify_api_key)):
    return {"user": user_email}
```

Use API keys:

```bash
curl -H "X-API-Key: key-for-user1" http://YOUR_IP/
```

---

## 3. Network-Level Security

**Best for:** Restricting access by IP address or network

### Option A: Authorized Networks (Cluster Access)

Restrict who can access the Kubernetes API:

```bash
# Enable authorized networks
gcloud container clusters update cluter-ai-agents \
  --region=europe-west4 \
  --enable-master-authorized-networks \
  --master-authorized-networks=YOUR_OFFICE_IP/32

# Add your home IP
gcloud container clusters update cluter-ai-agents \
  --region=europe-west4 \
  --master-authorized-networks=YOUR_OFFICE_IP/32,YOUR_HOME_IP/32
```

### Option B: Cloud Armor (Application Access)

Restrict application access by IP:

```bash
# Create security policy
gcloud compute security-policies create ip-whitelist-policy \
  --description="Allow only specific IPs"

# Add allowed IPs
gcloud compute security-policies rules create 1000 \
  --security-policy=ip-whitelist-policy \
  --expression="origin.ip in ['1.2.3.4/32', '5.6.7.8/32']" \
  --action=allow

# Deny all others
gcloud compute security-policies rules create 2000 \
  --security-policy=ip-whitelist-policy \
  --expression="true" \
  --action=deny-403

# Attach to backend service
gcloud compute backend-services update $BACKEND_SERVICE \
  --security-policy=ip-whitelist-policy \
  --global
```

### Option C: VPN or Private Cluster

For maximum security:

```bash
# Create private cluster (no public endpoints)
gcloud container clusters create-auto private-cluster \
  --region=europe-west4 \
  --enable-private-nodes \
  --enable-private-endpoint \
  --master-ipv4-cidr=172.16.0.0/28

# Access via Cloud VPN or IAP tunnel
gcloud compute start-iap-tunnel INSTANCE_NAME 22 \
  --local-host-port=localhost:2222
```

---

## 4. Comparison

| Method | Complexity | Cost | Email-Based | Custom Auth | Best For |
|--------|-----------|------|-------------|-------------|----------|
| **IAP** | Medium | Low | ✅ Yes | ❌ No | Google accounts |
| **OAuth in App** | High | Free | ✅ Yes | ✅ Yes | Custom logic |
| **API Keys** | Low | Free | ❌ No | ✅ Yes | API access |
| **IP Whit elist** | Low | Free | ❌ No | ❌ No | Fixed locations |
| **Private Cluster** | High | Medium | ❌ No | ❌ No | Maximum security |

---

## Quick Setup Scripts

### IAP Quick Setup

Save as `gke-deployment/scripts/4-setup-iap.sh`:

```bash
#!/bin/bash
set -e

PROJECT_ID="formare-ai"
ALLOWED_EMAILS=(
  "petrica.radan@formare.ai"
  "user2@formare.ai"
)

# Enable IAP
gcloud services enable iap.googleapis.com --project=$PROJECT_ID

echo "Next steps:"
echo "1. Create OAuth consent screen: https://console.cloud.google.com/apis/credentials/consent"
echo "2. Create OAuth credentials: https://console.cloud.google.com/apis/credentials"
echo "3. Run the kubectl commands to deploy IAP resources"
echo "4. Grant access to users"

for email in "${ALLOWED_EMAILS[@]}"; do
  echo "   gcloud iap web add-iam-policy-binding --member=user:$email ..."
done
```

---

## Recommended Approach

For your use case (specific email addresses), I recommend:

### ✅ **Use IAP** if

- Users have Google accounts (@formare.ai)
- Want enterprise-grade security
- Don't want to modify code

### ✅ **Use Application Auth** if

- Need custom authentication logic
- Users don't have Google accounts
- Want full control

### ✅ **Use Both** for

- Maximum security
- Defense in depth
- Compliance requirements

---

## Implementation Checklist

- [ ] Decide on authentication method
- [ ] Configure OAuth consent screen (if using IAP)
- [ ] Create OAuth credentials (if using IAP)
- [ ] Switch from LoadBalancer to Ingress (if using IAP)
- [ ] Apply Kubernetes resources
- [ ] Grant access to specific emails
- [ ] Test authentication
- [ ] Document access procedures
- [ ] Set up monitoring/alerts

---

## Need Help?

- IAP Documentation: <https://cloud.google.com/iap/docs>
- OAuth2 in FastAPI: <https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/>
- Cloud Armor: <https://cloud.google.com/armor/docs>

---

**Your application will now be secure and accessible only to authorized users!** 🔒
