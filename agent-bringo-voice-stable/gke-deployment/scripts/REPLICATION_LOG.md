# Security Replication Guide

To replicate the exact security setup (Workload Identity + IAP) for a new environment, use the provided scripts in this folder.

### 🚀 Standard Replication Flow

If you have already created your OAuth credentials in the Google Console, run this single command:

```bash
cd gke-deployment/scripts
./5-reproducible-security-bundle.sh <YOUR_CLIENT_ID> <YOUR_CLIENT_SECRET>
```

---

### 📂 Script Breakdown

1. **[2-setup-workload-identity.sh](2-setup-workload-identity.sh)**: Automates the creation of the GCP Service Account, grants BigQuery/Vertex AI permissions, and binds it to the Kubernetes Pods.
2. **[5-reproducible-security-bundle.sh](5-reproducible-security-bundle.sh)**: **Recommended.** This is the "Master Script" that orchestrates the entire security layer. It applies the BackendConfig, creates the secure Kubernetes secret, and registers your email with Google IAP.
3. **[6-debug-security.sh](6-debug-security.sh)**: Run this if the login isn't working. it will check every layer (IAM, K8s, Load Balancer) and tell you where the "leak" is.

### 🛡️ Manual Verification

After running the scripts, always check the **[IAP Dashboard](https://console.cloud.google.com/security/iap)** in Google Cloud. You should see a green toggle next to your Backend Service, and your email address should be listed under the "IAP-secured Web App User" role.
