#!/usr/bin/env bash
# Deploys the app, Load Balancer Service, HPA, and PodDisruptionBudget, then prints the public URL.
set -euo pipefail
source "$(dirname "$0")/config.env"
K8S="$(dirname "$0")/../k8s"

IMAGE="registry.digitalocean.com/$REGISTRY_NAME/$IMAGE_NAME:$IMAGE_TAG"

echo "==> Applying manifests (image: $IMAGE)"
kubectl apply -f "$K8S/00-namespace.yaml"
sed "s|IMAGE_PLACEHOLDER|$IMAGE|" "$K8S/01-deployment.yaml" | kubectl apply -f -
kubectl apply -f "$K8S/02-service-loadbalancer.yaml"
kubectl apply -f "$K8S/03-hpa.yaml"
kubectl apply -f "$K8S/04-pdb.yaml"

echo "==> Waiting for pods to be ready"
kubectl -n web-app rollout status deployment/web-app --timeout=180s

echo "==> Waiting for the DigitalOcean Load Balancer to get a public IP (2-4 minutes)"
for i in $(seq 1 40); do
  IP=$(kubectl -n web-app get svc web-app -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
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
