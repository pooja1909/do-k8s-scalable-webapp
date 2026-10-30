#!/usr/bin/env bash
# Default is a read-only plan. Preserve the registry unless explicitly selected.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
EXECUTE=false
DELETE_REGISTRY=false
for arg in "$@"; do
  case "$arg" in
    --execute) EXECUTE=true ;;
    --delete-registry) DELETE_REGISTRY=true ;;
    *) echo "Usage: $0 [--execute] [--delete-registry]" >&2; exit 1 ;;
  esac
done
verify_cluster_identity
if [ "$DELETE_REGISTRY" = true ]; then
  ACTUAL_REGISTRY=$(doctl registry get --format Name --no-header)
  if [ "$ACTUAL_REGISTRY" != "$REGISTRY_NAME" ]; then
    echo "Refusing: registry '$ACTUAL_REGISTRY' does not match '$REGISTRY_NAME'." >&2
    exit 1
  fi
fi
echo "Context: $EXPECTED_CONTEXT"
echo "Cluster: $CLUSTER_NAME ($CLUSTER_ID)"
echo "All workloads in this cluster would be deleted. Review these namespaces:"
kube get namespaces
echo "Plan: delete namespace web-app (including its LB), then cluster $CLUSTER_ID."
echo "Registry deletion selected: $DELETE_REGISTRY (registry: $REGISTRY_NAME)"
echo "Other associated volumes/snapshots/LBs are not force-deleted. Review leftovers afterward."
if [ "$EXECUTE" != true ]; then
  echo "Read-only plan complete. To proceed, rerun with --execute."
  exit 0
fi
read -r -p "Type 'delete $CLUSTER_ID' to delete this cluster and its workloads: " CONFIRM
if [ "$CONFIRM" != "delete $CLUSTER_ID" ]; then echo "Cancelled."; exit 1; fi
if [ "$DELETE_REGISTRY" = true ]; then
  read -r -p "Type '$REGISTRY_NAME' to also delete ALL images in that registry: " CONFIRM_REGISTRY
  if [ "$CONFIRM_REGISTRY" != "$REGISTRY_NAME" ]; then echo "Cancelled."; exit 1; fi
fi
# Verify again immediately before mutation; never suppress a failed deletion.
CONFIRMED_ID=$CLUSTER_ID
verify_cluster_identity
if [ "$CLUSTER_ID" != "$CONFIRMED_ID" ]; then echo "Cluster changed; refusing." >&2; exit 1; fi
kube --request-timeout=330s delete namespace web-app --ignore-not-found --wait=true --timeout=5m
# No --dangerous: do not blindly delete associated shared resources.
doctl kubernetes cluster delete "$CLUSTER_ID" --force
if [ "$DELETE_REGISTRY" = true ]; then
  ACTUAL_REGISTRY=$(doctl registry get --format Name --no-header)
  if [ "$ACTUAL_REGISTRY" != "$REGISTRY_NAME" ]; then echo "Registry changed; refusing." >&2; exit 1; fi
  doctl registry delete  # retain doctl's confirmation; no --force
fi
echo "Review remaining billable resources; do not assume all charges have stopped:"
doctl compute load-balancer list
doctl compute volume list
