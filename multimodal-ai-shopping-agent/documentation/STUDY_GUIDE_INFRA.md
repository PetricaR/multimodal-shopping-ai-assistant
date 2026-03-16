# 🎓 Study Guide: Kubernetes (GKE) & Production AI Infrastructure

This guide is for engineers who want to learn how to deploy and manage AI applications in a real-world, scalable "Cloud-Native" environment.

---

## 1. Containerization: The "Universal Box"

### What is Docker?

Before Kubernetes, "it worked on my machine" was a common problem. **Docker** packages your code, your Python version, and all your libraries into a single **Image**.

- **Technical Term: Immutable**: Once an image is built (e.g., `bringo-api:v1`), it never changes. Whether you run it on your laptop or a massive Google server, it behaves identicaly.
- **Dockerfile**: The "recipe" for building this box. Ours starts with `python:3.11-slim` to keep the size small and the security tight.

---

## 2. Kubernetes (GKE): The "Conductor"

If a Docker container is a musician, **Kubernetes** is the **Conductor** of the orchestra. In this project, we use **GKE Autopilot**.

### Core Concepts to Learn

- **Pod**: The smallest unit in Kubernetes. Think of it as a single instance of your API.
- **Deployment**: The "manager" of your pods. It ensures that if you want 3 copies of your API running, and one crashes, a new one is started immediately.
- **Service (Load Balancer)**: The "Receptionist." It provides a single IP address for the whole world to talk to. Even if your pods are moving around or restarting, the Service ensures the traffic always gets to a healthy one.

### GKE Autopilot vs. Standard

- **Standard**: You manage the servers (Virtual Machines).
- **Autopilot**: Google manages the servers for you. You only care about your **Pods**. It's the modern way to deploy because it minimizes "Ops" (Operational work).

---

## 3. Workload Identity: Security for the AI Era

In the old days, you would download a `key.json` file and put it in your code to talk to BigQuery. **This is dangerous.** If that file is stolen, your data is gone.

### How Workload Identity Works (The "Secret-less" Way)

1. **Trust**: We tell Google Cloud: "I trust any Pod running in this specific GKE cluster."
2. **Impersonation**: When our code needs to talk to BigQuery, it doesn't use a password. Instead, it asks GKE for a temporary token.
3. **Identity**: GKE "proves" to the BigQuery API that the Pod is who it says it is.

- **Learning Takeaway**: This is called **Principle of Least Privilege**. Each part of our app only gets the *exact* permissions it needs, and nothing more.

---

## 4. Autoscaling: Handling the "Black Friday" Spike

How does our API handle 10 users one minute and 10,000 the next?

- **HPA (Horizontal Pod Autoscaler)**: It watches the CPU usage of our pods.
- **Metric**: If average CPU usage goes over 70%, the HPA tells the cluster: "Spin up 5 more Pods!"
- **Multimodal Factor**: Image processing is "heavy" on the CPU. By scaling on CPU, we ensure our API stays responsive even when analyzing many product photos at once.

---

## 5. CI/CD: The "Automated Factory" line

Every time we run `deploy-gke.sh`, we are performing a **Manual CI/CD** flow:

1. **Build**: Create the new Docker image.
2. **Push**: Store it in the **Google Artifact Registry** (a library for your Docker boxes).
3. **Apply**: Tell Kubernetes to update the cluster with the new version.

- **Technical Term: Rolling Update**: Kubernetes doesn't kill all your old versions at once. It starts one "new" pod, waits for it to become healthy, and then kills one "old" pod. This means **Zero Downtime**.

---

## 6. Networking: L4 vs L7 (The "API Shield" Choice)

In this project, we made a deep architectural decision to use an **L4 Regional Load Balancer** protected by an **API Shield**.

### The Problem: Global Ingress (L7) Complexity

Standard Google Ingress (L7) is designed for websites with domain names (like `google.com`). When using raw IP addresses for testing, it creates an "SSL Protocol Error" because it expects a valid certificate.

### The Solution: L4 + API Shield

1. **L4 (Layer 4)**: This Load Balancer is like a "Fast Lane." It just passes traffic directly to your pods without looking at the content. It's extremely fast and stable.
2. **API Shield (The Key)**: Since anyone can find a public IP, we added a "Private Passcode." Every request from the frontend to the API must include a secret `X-API-KEY`.
3. **Defense in Depth**: We use **Google Authentication** on the Streamlit dashboard and an **API Key** for the backend.

---

## 🔑 Infrastructure Terms Dictionary

| Term | Simple Definition |
| :--- | :--- |
| **Namespace** | A "folder" inside Kubernetes to keep different projects separate. |
| **Readiness Probe** | A test Kubernetes runs to see if the API is "awake" and ready to take traffic. |
| **Liveness Probe** | A test to see if the API has "frozen" and needs to be restarted. |
| **Resource Limits** | Telling Kubernetes exactly how much RAM and CPU a pod is allowed to use. |
| **Ingress** | A more advanced Load Balancer that can handle complex routing and SSL certificates. |
