# Setup and Operations Guide

Prepared for the customer's engineering team. Allow about 45 minutes for first-time setup; provisioning and autoscaling times vary.

## 1. Architecture and prerequisites

The Node.js app listens on port 8080. A Service exposes HTTP traffic on port 80 through a regional network Load Balancer. DOKS manages node health checks; Kubernetes uses `/healthz` for liveness and `/readyz` for readiness. The HPA owns the app replica count, targeting 50% of the 100m CPU request. Cluster Autoscaler adds nodes when eligible pods cannot be scheduled, within a 2-4 node pool.

Install `doctl`, `kubectl`, Docker with buildx, Python 3, and optionally `hey`. On macOS: `brew install doctl kubectl hey`; install Docker Desktop separately. Authenticate with `doctl auth init`. Never put API tokens in this repository.

Observed on October 30, 2026: **doctl 2.1.0**, **kubectl v1.36.1**, **DOKS 1.37.0-do.2**. Local regression tests used Node **v24.22.1**, plus the Node 22 Alpine linux/amd64 container. See `evidence/local/` and `evidence/final/baseline/versions.json` for exact output. These are observed versions; check availability before creating a new cluster.

## 2. Configure and create

```bash
git clone https://github.com/pooja1909/do-k8s-scalable-webapp.git
cd do-k8s-scalable-webapp
```

Edit `scripts/config.env`: registry name, region, cluster/pool names, node size and bounds, image tag, and Kubernetes version. The sample registry is `pooja-doks-demo-2026`, matching the existing demo. Use a unique registry for another account. Check available versions with `doctl kubernetes options versions` before new creation.

```bash
./scripts/01-create-infra.sh
```

The creation script explicitly uses `--ha=true`, the selected `--version`, a 2-4 node autoscaling pool, and the metrics-server add-on. It verifies an existing registry if creation fails, connects registry access, saves kubeconfig, and waits for metrics. It returns failure if metrics remain unavailable. This step creates billable resources; skip it when updating the existing cluster.

## 3. Build and deploy

```bash
./scripts/02-build-push.sh
kubectl config current-context
./scripts/03-deploy.sh
```

Buildx targets `linux/amd64`. Use a unique image tag for each release; this submission uses **1.0.2**. Deployment substitutes the same tag into `APP_VERSION`. The deployment script verifies context `do-<region>-<cluster>` and matches its API endpoint against the DigitalOcean cluster before making changes.

It applies the namespace and HPA, safely migrates replica ownership, applies the app, Service, and PDB, waits for rollout and at least two available pods, then prints the Load Balancer URL. The Service explicitly selects `REGIONAL_NETWORK` with TCP forwarding and leaves health checks under DOKS control.

<!-- PAGEBREAK -->

### HPA ownership of replicas

The HPA owns the live replica count. If a saved client-side apply configuration contains `spec.replicas`, removing that field from the manifest alone can reset the live Deployment to one replica. The script updates `kubectl.kubernetes.io/last-applied-configuration`, removing **only** `spec.replicas`, before applying the replica-free manifest. Other saved fields stay intact so ordinary deletions continue to work. Deployments therefore preserve the HPA's live replica count.

This automates the [Kubernetes migration procedure](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/#migrating-deployments-and-statefulsets-to-horizontal-autoscaling). A fresh Deployment may start with the API default of one until HPA reconciliation; the script does not announce readiness until two are available. Do not use `kubectl scale` or remove the live replica field during migration.

## 4. Verify and collect evidence

```bash
kubectl -n web-app get pods -o wide
kubectl -n web-app get hpa web-app
kubectl -n web-app get svc web-app
kubectl top nodes
./scripts/demo-load-balancing.sh
./scripts/capture-evidence.sh baseline
./scripts/benchmark.sh light
./scripts/benchmark.sh work
```

Run the benchmarks sequentially without internal load-generator traffic. The script requires two ready replicas and an idle HPA before each run and verifies the live app version. Defaults: `hey -z 60s -c 50 -disable-keepalive`; the work test uses `/work?ms=50`. Fresh connections allow new pods to receive new traffic. Set `KEEP_ALIVE=true` for a separate persistent-connection stress test. Each test saves raw output, command, image/digest, versions, and HPA/pod/node snapshots. Recovery-folder numbers count sleep intervals; use recorded timestamps for elapsed time.

For screenshots, capture the cluster HA and node-pool settings and the Load Balancer health-check settings in the DigitalOcean control panel, record capture time, and keep them alongside the raw API snapshots. Do not label a diagram or reconstructed display as a dashboard screenshot.

<!-- PAGEBREAK -->

## 5. Operate and troubleshoot

| Task or symptom | Action |
| --- | --- |
| New version | Change `IMAGE_TAG`, build/push, then run `03-deploy.sh`. Record errors/latency throughout a rollout before claiming no downtime. |
| Rollback | `kubectl -n web-app rollout undo deployment/web-app`; then align source/tag with the rollback before the next deploy. |
| HPA unknown | Check `kubectl top pods -n web-app`, CPU requests, and `kubectl -n web-app describe hpa web-app`. |
| Pods pending | Inspect scheduler events, allocatable resources, taints, spread constraints, pool max and account limits. High CPU alone does not trigger node scaling. |
| Image pull failure | Verify registry name/tag and cluster registry integration with `doctl kubernetes cluster registry add <cluster>`. |
| Wrong image architecture | Rebuild using `--platform linux/amd64`. |
| LB unhealthy | Inspect effective LB config with `doctl compute load-balancer get <id> -o json`, Service annotations, endpoint slices, node health, and pod readiness. Do not assume the LB is probing the app. |
| Pods share a node after scale-down | Check both workers are Ready and schedulable. Run the monitored pod-recovery procedure below, then verify one ready replica per worker. Evaluate automated rebalancing for production. |

At an idle two-pod baseline, run `python3 scripts/reliability-check.py pod-recovery` to inspect the plan, then add `--execute` to evict one pod through the PDB. The script logs HTTP samples at up to 10 requests/second and cluster state every two seconds, waits for two ready replicas, and records 20 seconds of post-recovery traffic. It never stops a worker. For a release, use the `rollout --execute` action to monitor the deployment script. Each action preserves its evidence and refuses to overwrite an existing run directory.

Topology constraints act when pods are scheduled; they do not rebalance existing pods. The PDB limits voluntary evictions only. `maxUnavailable: 0` is a rollout setting, not proof of application uptime. HA's 99.95% SLA covers the control plane only.

## 6. Teardown and billing review

```bash
./scripts/99-teardown.sh
./scripts/99-teardown.sh --execute
# Only for a registry dedicated to this demo:
./scripts/99-teardown.sh --execute --delete-registry
```

The default prints a plan and namespace inventory. Execution requires a typed cluster ID. The script verifies both context and cluster endpoint, deletes the app namespace before the cluster, stops on errors, and does not use `--dangerous`. Registry deletion is opt-in, requires exact name verification and separate confirmation, and retains doctl's own prompt. Check remaining LBs, volumes, snapshots, and the billing dashboard; successful cluster deletion alone is not proof that all charges stopped.

Recommend a **$120 billing alert**, subject to the customer's agreed account-wide budget, plus CPU, HPA metric, readiness, latency, and error alerts. An alert does not stop spending.
