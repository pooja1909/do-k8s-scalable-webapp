# Setup Guide: Running the Web App on DigitalOcean Kubernetes

This guide is written for the customer's engineering team. It explains what each piece does and how to deploy, operate,
and troubleshoot it. Plan for about 45 minutes the first time.

## 1. What you're building

- **App:** a Node.js web app packaged as a Docker image.
- **Registry:** DigitalOcean Container Registry (DOCR) stores the image.
- **Cluster:** a DigitalOcean Kubernetes (DOKS) cluster with one node pool of 2–4 Basic Droplets that grows and shrinks
  automatically.
- **Load Balancer:** a DigitalOcean Load Balancer gives the app a public IP and spreads traffic across the nodes. It
  only sends traffic to nodes that pass the `/healthz` health check.
- **Autoscaling:** the Horizontal Pod Autoscaler (HPA) adds app pods when CPU passes 50%. When the nodes are full, the
  Cluster Autoscaler adds nodes.

See `docs/architecture.png` for the diagram.

## 2. Install the tools (one time)

| Tool | Install | Check |
| --- | --- | --- |
| doctl | `brew install doctl` | `doctl version` |
| kubectl | `brew install kubectl` | `kubectl version --client` |
| Docker Desktop | docker.com | `docker buildx version` |
| hey (optional) | `brew install hey` | `hey` |

Then connect doctl to your account. Create an API token in the DigitalOcean control panel (**API → Generate New
Token**, read and write) and run:

```bash
doctl auth init
```

## 3. Configure

Open `scripts/config.env` and set:

- `REGISTRY_NAME`: must be unique across all of DigitalOcean (for example, add your company name).
- `REGION`: pick the region closest to your users (`doctl kubernetes options regions`).
- `MIN_NODES` / `MAX_NODES`: keep the minimum at 2 for availability. The maximum caps your spend.

## 4. Create the infrastructure

```bash
./scripts/01-create-infra.sh
```

This creates the registry and the cluster, installs **metrics-server** (the HPA needs it to read CPU), connects the
registry to the cluster, and saves your kubectl credentials. It takes 5–7 minutes.

Check: `kubectl get nodes` shows 2 nodes `Ready`, and `kubectl top nodes` shows CPU numbers.

## 5. Build and push the image

```bash
./scripts/02-build-push.sh
```

The script builds for `linux/amd64`, because DOKS nodes are amd64. On an Apple Silicon Mac, an image built without this
flag fails with `exec format error`.

## 6. Deploy

```bash
./scripts/03-deploy.sh
```

This applies five Kubernetes files, in order:

| File | What it does |
| --- | --- |
| `00-namespace.yaml` | Creates the `web-app` namespace, keeping the app separate from system components. |
| `01-deployment.yaml` | Runs the app: at least 2 pods spread across nodes, CPU/memory requests and limits, health probes, rolling updates with no downtime. |
| `02-service-loadbalancer.yaml` | Creates the DigitalOcean Load Balancer with a health check on `/healthz`. |
| `03-hpa.yaml` | Autoscaling rules: 2–10 pods, target 50% CPU. |
| `04-pdb.yaml` | Keeps at least 1 pod running during node maintenance. |

The script prints the public URL when the Load Balancer is ready (2–4 minutes).

## 7. Verify

```bash
kubectl -n web-app get pods -o wide     # pods Running, on different nodes
kubectl -n web-app get svc web-app      # EXTERNAL-IP is set
kubectl -n web-app get hpa              # TARGETS shows a number like 2%/50%, not <unknown>
./scripts/demo-load-balancing.sh        # requests spread across pods
```

## 8. Day-2 operations

| Task | Command |
| --- | --- |
| Deploy a new version | Change `IMAGE_TAG` in `config.env`, then run `02-build-push.sh` and `03-deploy.sh`. The rollout has no downtime. |
| Roll back | `kubectl -n web-app rollout undo deployment/web-app` |
| Watch scaling | `./scripts/demo-autoscaling.sh watch` |
| Check logs | `kubectl -n web-app logs -l app=web-app --tail=50` |
| Change scaling limits | Edit `k8s/03-hpa.yaml` (pods) or run `doctl kubernetes cluster node-pool update <cluster> <pool> --min-nodes N --max-nodes M` (nodes) |
| Upgrade Kubernetes | Control panel → Kubernetes → cluster → **Upgrade**, or turn on automatic upgrades. The PodDisruptionBudget keeps the app serving while nodes are replaced. |

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| HPA shows `<unknown>/50%` | metrics-server not ready, or pods have no CPU request | Wait 1–2 minutes; check `kubectl top pods -n web-app`. |
| `ImagePullBackOff` | Cluster can't reach the registry | `doctl kubernetes cluster registry add <cluster>` |
| `CrashLoopBackOff` with `exec format error` | Image built for ARM | Rebuild with `--platform linux/amd64`. |
| Pods `Pending` under load | No room on the current nodes | Expected: the Cluster Autoscaler adds a node in a few minutes. If it doesn't, check `MAX_NODES` and the account Droplet limit (25 by default). |
| Load Balancer shows unhealthy nodes | Health check failing | `curl http://<node-ip>:<nodeport>/healthz`; check the pod logs. |

## 10. Clean up

```bash
./scripts/99-teardown.sh
```

Deletes the Load Balancer, the cluster, and the registry so nothing keeps billing.
