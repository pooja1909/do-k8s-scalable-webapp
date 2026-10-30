# Scalable Web App on DigitalOcean Kubernetes (DOKS)

A containerized Node.js web app deployed on DigitalOcean Kubernetes, behind a DigitalOcean Load Balancer, with
Horizontal Pod Autoscaling for pods and Cluster Autoscaling for nodes. It was built for a SaaS customer whose goals are
**scalability, performance, reliability, and cost optimization**.

![Architecture](docs/architecture.png)

## What's in this repo

| Path | What it is |
| --- | --- |
| `app/server.js` | Node.js web app (no dependencies). Shows which pod and node served each request. |
| `app/Dockerfile` | Small Alpine-based image that runs as a non-root user. |
| `k8s/00-namespace.yaml` | `web-app` namespace. |
| `k8s/01-deployment.yaml` | Deployment: 2+ replicas spread across nodes, CPU/memory requests, health probes, zero-downtime rolling updates. |
| `k8s/02-service-loadbalancer.yaml` | Service of type `LoadBalancer`; DOKS creates a DigitalOcean Load Balancer with an HTTP health check. |
| `k8s/03-hpa.yaml` | Horizontal Pod Autoscaler: 2–10 pods, targets 50% average CPU. |
| `k8s/04-pdb.yaml` | PodDisruptionBudget: at least one pod stays up during node upgrades and scale-down. |
| `k8s/load-generator.yaml` | Demo-only traffic generator that drives CPU up to trigger autoscaling. |
| `scripts/` | Create infrastructure, build and push the image, deploy, run the demos, benchmark, tear down. |
| `docs/` | Architecture diagram, setup guide, cost and performance analysis, QBR summary. |

## How it meets the customer's goals

| Goal | How |
| --- | --- |
| Scalability | HPA adds pods when CPU passes 50% (2 → 10 pods). The Cluster Autoscaler adds nodes when pods don't fit (2 → 4 nodes). |
| Performance | Small CPU requests pack pods densely (to be raised from production data, see QBR); the HPA adds pods as soon as it measures a spike (no scale-up wait window); traffic is spread across all pods. |
| Reliability | At least 2 pods on separate nodes, Load Balancer and readiness health checks, graceful shutdown, zero-downtime rolling updates, and a PodDisruptionBudget. |
| Cost optimization | Starts small (2 Basic nodes) and only pays for extra capacity while it's needed. Max replicas and max nodes cap spend. Free registry tier; HA control plane ($40/month) for a 99.95% SLA. |

## Prerequisites

- A DigitalOcean account with an [API token](https://docs.digitalocean.com/reference/api/create-personal-access-token/)
- [`doctl`](https://docs.digitalocean.com/reference/doctl/how-to/install/) — then run `doctl auth init`
- [`kubectl`](https://kubernetes.io/docs/tasks/tools/)
- [Docker](https://docs.docker.com/get-docker/) with `buildx` (included in Docker Desktop)
- Optional: [`hey`](https://github.com/rakyll/hey) for the benchmark (`brew install hey`)

## Deploy in 4 steps (about 15 minutes)

```bash
# 0. Set a globally unique registry name and your region
vi scripts/config.env

# 1. Create the registry and the DOKS cluster (autoscaling node pool + metrics-server)
./scripts/01-create-infra.sh

# 2. Build the image for linux/amd64 and push it to DigitalOcean Container Registry
./scripts/02-build-push.sh

# 3. Deploy the app, Load Balancer, HPA, and PodDisruptionBudget; prints the public URL
./scripts/03-deploy.sh
```

Open the printed URL and refresh: the pod name changes as the Load Balancer spreads traffic.

## Demo

**Load balancing** — counts which pod served each of 30 requests:

```bash
./scripts/demo-load-balancing.sh
```

**Autoscaling** — use two terminals:

```bash
# Terminal 1: live view of the HPA, pod CPU, pods per node, and nodes
./scripts/demo-autoscaling.sh watch

# Terminal 2: start load, then make it heavier, then stop it
./scripts/demo-autoscaling.sh start
./scripts/demo-autoscaling.sh more
./scripts/demo-autoscaling.sh stop      # pods scale back down to 2 within about 1–2 minutes
```

**Benchmark** — response times through the Load Balancer:

```bash
./scripts/benchmark.sh          # light endpoint
./scripts/benchmark.sh work     # CPU-heavy endpoint
```

## Run the app locally (optional)

```bash
cd app && node server.js        # http://localhost:8080
# or
docker build -t web-app ./app && docker run -p 8080:8080 web-app
```

## Clean up (stop all charges)

```bash
./scripts/99-teardown.sh
```

This deletes the namespace first (so DOKS removes the Load Balancer), then the cluster and the registry, and lists any
leftover Load Balancers or volumes.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| HPA shows `<unknown>/50%` | metrics-server isn't ready yet. Wait a minute; check `kubectl top nodes`. |
| Pods stuck in `ImagePullBackOff` | Run `doctl kubernetes cluster registry add <cluster>` and check the image name in `config.env`. |
| `exec format error` in pod logs | The image was built for ARM. Rebuild with `--platform linux/amd64` (the build script does this). |
| Load Balancer has no IP | It takes 2–4 minutes. Watch with `kubectl -n web-app get svc web-app -w`. |
| Pods stay `Pending` under load | Nodes are full; the Cluster Autoscaler adds a node in a few minutes (up to `MAX_NODES`). |
