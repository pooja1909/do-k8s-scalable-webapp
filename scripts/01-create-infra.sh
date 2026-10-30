#!/usr/bin/env bash
# Creates the DigitalOcean infrastructure:
#   1. A Container Registry (DOCR) to store the app image
#   2. A DOKS cluster with an autoscaling node pool and the metrics-server add-on (needed by the HPA)
#   3. Registry access for the cluster, and kubectl credentials on this machine
# Prerequisites: doctl installed and authenticated (`doctl auth init`), kubectl installed.
set -euo pipefail
source "$(dirname "$0")/config.env"

echo "==> Creating container registry '$REGISTRY_NAME' (Starter plan, free: 1 repo, 500 MiB)"
doctl registry create "$REGISTRY_NAME" --subscription-tier starter --region "$REGION" || \
  echo "    (registry may already exist; continuing)"

echo "==> Creating DOKS cluster '$CLUSTER_NAME' in $REGION (takes ~5-7 minutes)"
doctl kubernetes cluster create "$CLUSTER_NAME" \
  --region "$REGION" \
  --node-pool "name=$NODE_POOL;size=$NODE_SIZE;count=$MIN_NODES;auto-scale=true;min-nodes=$MIN_NODES;max-nodes=$MAX_NODES" \
  --1-clicks metrics-server \
  --wait

echo "==> Letting the cluster pull images from the registry"
doctl kubernetes cluster registry add "$CLUSTER_NAME"

echo "==> Saving kubectl credentials"
doctl kubernetes cluster kubeconfig save "$CLUSTER_NAME"

echo "==> Nodes:"
kubectl get nodes -o wide

echo "==> Waiting for metrics-server (the HPA needs it)..."
for i in $(seq 1 30); do
  if kubectl top nodes >/dev/null 2>&1; then
    kubectl top nodes
    echo "Infrastructure ready."
    exit 0
  fi
  sleep 10
done
echo "metrics-server is not reporting yet. Check: kubectl get pods -A | grep metrics-server"
