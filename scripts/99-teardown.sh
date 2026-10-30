#!/usr/bin/env bash
# Deletes everything so nothing keeps billing after the demo.
# Delete the Service first so DOKS removes the Load Balancer it created.
set -euo pipefail
source "$(dirname "$0")/config.env"

echo "==> Deleting app namespace (removes the Load Balancer)"
kubectl delete namespace web-app --ignore-not-found --wait=true || true

echo "==> Deleting cluster '$CLUSTER_NAME'"
doctl kubernetes cluster delete "$CLUSTER_NAME" --force --dangerous || true

echo "==> Deleting registry '$REGISTRY_NAME'"
doctl registry delete --force || true

echo "==> Check for anything left over:"
doctl compute load-balancer list
doctl compute volume list
