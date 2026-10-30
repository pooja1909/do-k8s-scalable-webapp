#!/usr/bin/env bash
# Shared read-only identity checks.
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/config.env"
require_context() {
  EXPECTED_CONTEXT="do-$REGION-$CLUSTER_NAME"
  CURRENT_CONTEXT=$(kubectl config current-context)
  if [ "$CURRENT_CONTEXT" != "$EXPECTED_CONTEXT" ]; then
    echo "Refusing: context '$CURRENT_CONTEXT'; expected '$EXPECTED_CONTEXT'." >&2
    return 1
  fi
}
kube() { kubectl --context "$EXPECTED_CONTEXT" --request-timeout=20s "$@"; }
verify_cluster_identity() {
  require_context
  local details actual_server expected_server
  details=$(doctl kubernetes cluster get "$CLUSTER_NAME" --output json)
  CLUSTER_ID=$(printf '%s' "$details" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["id"])')
  expected_server=$(printf '%s' "$details" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["endpoint"])')
  actual_server=$(kube config view --minify -o jsonpath='{.clusters[0].cluster.server}')
  if [ -z "$CLUSTER_ID" ] || [ "$actual_server" != "$expected_server" ]; then
    echo "Refusing: kubeconfig server does not match the DigitalOcean cluster endpoint." >&2
    return 1
  fi
}
