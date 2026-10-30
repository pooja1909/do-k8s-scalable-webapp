#!/usr/bin/env bash
# Read-only snapshot; never exports kubeconfig credentials or Kubernetes Secrets.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_context
LABEL=${1:-snapshot}
case "$LABEL" in *[!a-zA-Z0-9_-]*|'') echo "Invalid snapshot label" >&2; exit 1;; esac
ROOT=${2:-"$SCRIPT_DIR/../evidence/runs/$(date -u +%Y%m%dT%H%M%SZ)"}
OUT="$ROOT/$LABEL"
mkdir -p "$OUT"
record() {
  local filename=$1
  shift
  printf '%s ' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$OUT/commands.txt"
  printf '%q ' "$@" >> "$OUT/commands.txt"
  printf '\n' >> "$OUT/commands.txt"
  local result=0
  "$@" > "$OUT/$filename" 2> "$OUT/$filename.stderr.txt" || result=$?
  printf 'exit=%s\n' "$result" >> "$OUT/commands.txt"
  if [ "$result" -ne 0 ]; then echo "Capture warning: $filename (exit $result)" >&2; fi
}
record context.txt kubectl config current-context
record versions.json kube version -o json
record doctl-version.txt doctl version
record deployment.json kube -n web-app get deployment web-app -o json
record hpa.json kube -n web-app get hpa web-app -o json
record pods.json kube -n web-app get pods -o json
record nodes.json kube get nodes -o json
record service.json kube -n web-app get service web-app -o json
record endpoints.json kube -n web-app get endpointslices -l kubernetes.io/service-name=web-app -o json
record events.json kube -n web-app get events -o json
record pod-metrics.txt kube -n web-app top pods
record node-metrics.txt kube top nodes
record cluster.json doctl kubernetes cluster get "$CLUSTER_NAME" -o json
LB_ID=$(kube -n web-app get svc web-app -o jsonpath='{.metadata.annotations.kubernetes\.digitalocean\.com/load-balancer-id}')
if [ -n "$LB_ID" ]; then
  record load-balancer.json doctl compute load-balancer get "$LB_ID" -o json
else
  echo "No DOKS LB identifier found; effective LB settings not captured." > "$OUT/load-balancer-missing.txt"
fi
echo "Snapshot saved: $OUT"
