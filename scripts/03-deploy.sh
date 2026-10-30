#!/usr/bin/env bash
# Deploys the app, Load Balancer Service, HPA, and PodDisruptionBudget, then prints the public URL.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
K8S="$(dirname "$0")/../k8s"
verify_cluster_identity
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

IMAGE="registry.digitalocean.com/$REGISTRY_NAME/$IMAGE_NAME:$IMAGE_TAG"

echo "==> Applying manifests (image: $IMAGE)"
kube apply -f "$K8S/00-namespace.yaml"
kube apply -f "$K8S/03-hpa.yaml"
# Edit historical ownership before applying the replica-free manifest. Clearing
# live spec.replicas would default it to 1; never patch or scale that live field.
kube -n web-app get deployment web-app --ignore-not-found -o json > "$WORK_DIR/current.json"
if [ -s "$WORK_DIR/current.json" ]; then
  python3 "$SCRIPT_DIR/migrate-replicas.py" < "$WORK_DIR/current.json" > "$WORK_DIR/last-applied.json"
  if [ -s "$WORK_DIR/last-applied.json" ]; then
    kube apply set-last-applied -f "$WORK_DIR/last-applied.json"
  fi
fi
sed -e "s|IMAGE_PLACEHOLDER|$IMAGE|" -e "s|VERSION_PLACEHOLDER|$IMAGE_TAG|" \
  "$K8S/01-deployment.yaml" | kube apply -f -
kube apply -f "$K8S/02-service-loadbalancer.yaml"
kube apply -f "$K8S/04-pdb.yaml"

echo "==> Waiting for pods to be ready"
kube --request-timeout=200s -n web-app rollout status deployment/web-app --timeout=180s
# A fresh Deployment defaults to 1 until HPA reconciliation. Wait for its minimum.
for i in $(seq 1 36); do
  AVAILABLE=$(kube -n web-app get deployment web-app -o jsonpath='{.status.availableReplicas}')
  if [ "${AVAILABLE:-0}" -ge 2 ]; then break; fi
  sleep 5
done
if [ "${AVAILABLE:-0}" -lt 2 ]; then
  echo "HPA minimum not ready; inspect HPA conditions and pod events." >&2
  exit 1
fi

echo "==> Waiting for the DigitalOcean Load Balancer to get a public IP (2-4 minutes)"
for i in $(seq 1 40); do
  IP=$(kube -n web-app get svc web-app -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
  if [ -n "$IP" ]; then
    echo ""
    echo "App is live:  http://$IP"
    echo "JSON info:    http://$IP/api/info"
    exit 0
  fi
  printf "."
  sleep 10
done
echo ""
echo "Load Balancer still provisioning. Check: kubectl -n web-app get svc web-app -w"
exit 1
