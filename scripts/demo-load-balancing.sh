#!/usr/bin/env bash
# Demo 1: show the Load Balancer spreading requests across pods and nodes.
# Sends N requests (default 30) and counts how many each pod served.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_context
IP=$(kube -n web-app get svc web-app -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
N=${1:-30}

echo "Sending $N requests to http://$IP/api/info ..."
for i in $(seq 1 "$N"); do
  # Each curl is a new connection, so the Load Balancer picks a target every time.
  # The trailing echo puts each response on its own line so they can be counted.
  curl --fail --silent --show-error --max-time 10 "http://$IP/api/info" | sed -E 's/.*"pod":"([^"]+)","node":"([^"]+)".*/\1  (node: \2)/'
  echo
done | grep -v '^$' | sort | uniq -c | sort -rn
