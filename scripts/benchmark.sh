#!/usr/bin/env bash
# Capture raw hey output plus before/during/after/recovery snapshots.
# Usage: ./scripts/benchmark.sh [light|work]
# DURATION=60s CONCURRENCY=50 RECOVERY_SECONDS=120 are the defaults.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
verify_cluster_identity
MODE=${1:-light}
case "$MODE" in light|work) ;; *) echo "Usage: $0 [light|work]" >&2; exit 1;; esac
DURATION=${DURATION:-60s}
CONCURRENCY=${CONCURRENCY:-50}
RECOVERY_SECONDS=${RECOVERY_SECONDS:-120}
KEEP_ALIVE=${KEEP_ALIVE:-false}
case "$KEEP_ALIVE" in true|false) ;; *) echo "KEEP_ALIVE must be true or false." >&2; exit 1;; esac
HEY_ARGS=(-z "$DURATION" -c "$CONCURRENCY")
if [ "$KEEP_ALIVE" = false ]; then HEY_ARGS+=(-disable-keepalive); fi
case "$CONCURRENCY:$RECOVERY_SECONDS" in *[!0-9:]*|'') echo "Use numeric concurrency/recovery." >&2; exit 1;; esac
if [ "$CONCURRENCY" -lt 1 ]; then echo "Concurrency must be positive." >&2; exit 1; fi
command -v hey >/dev/null
# Require the same idle baseline for each endpoint measurement.
kube -n web-app get deployment,hpa,pods -o json | python3 -c '
import json,sys
items=json.load(sys.stdin)["items"]
deployment=next(x for x in items if x["kind"]=="Deployment" and x["metadata"]["name"]=="web-app")
hpa=next(x for x in items if x["kind"]=="HorizontalPodAutoscaler" and x["metadata"]["name"]=="web-app")
pods=[x for x in items if x["kind"]=="Pod"]
ready=lambda p: not p["metadata"].get("deletionTimestamp") and any(c["type"]=="Ready" and c["status"]=="True" for c in p.get("status",{}).get("conditions",[]))
if not (deployment["spec"].get("replicas")==2 and hpa["status"].get("currentReplicas")==2 and hpa["status"].get("desiredReplicas")==2 and len(pods)==2 and all(ready(p) and p["metadata"].get("labels",{}).get("app")=="web-app" for p in pods)):
    sys.exit("Wait for two ready replicas, idle HPA, and no load generator before benchmarking.")
'
IP=$(kube -n web-app get svc web-app -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
if [ -z "$IP" ]; then echo "Load Balancer has no public IP." >&2; exit 1; fi
URL="http://$IP/api/info"
if [ "$MODE" = work ]; then URL="http://$IP/work?ms=50"; fi
OUT=${EVIDENCE_DIR:-"$SCRIPT_DIR/../evidence/runs/$(date -u +%Y%m%dT%H%M%SZ)-$MODE"}
if [ -e "$OUT" ]; then echo "Refusing to overwrite evidence directory: $OUT" >&2; exit 1; fi
mkdir -p "$OUT"
{
  date -u +started_at=%Y-%m-%dT%H:%M:%SZ
  printf 'command=hey '; printf '%q ' "${HEY_ARGS[@]}" "$URL"; printf '\n'
  printf 'keep_alive=%s\n' "$KEEP_ALIVE"
  printf 'context=%s\nmode=%s\nduration=%s\nconcurrency=%s\nrecovery_seconds=%s\n' "$EXPECTED_CONTEXT" "$MODE" "$DURATION" "$CONCURRENCY" "$RECOVERY_SECONDS"
  printf 'source_sha256='
  shasum -a 256 "$SCRIPT_DIR/../app/server.js"
  printf 'Note: source hash is local; deployed image/digest are in deployment.json and pods.json.\n'
} > "$OUT/metadata.txt"
bash "$SCRIPT_DIR/capture-evidence.sh" before "$OUT"
curl --fail --silent --show-error --max-time 10 "$URL" > "$OUT/endpoint-before.json"
curl --fail --silent --show-error --max-time 10 "http://$IP/api/info" > "$OUT/release-before.json"
python3 - "$OUT/release-before.json" "$IMAGE_TAG" <<'PY'
import json,sys
if json.load(open(sys.argv[1])).get('version') != sys.argv[2]:
    sys.exit('Live version does not match configured image tag; deploy before benchmarking.')
PY
echo "Benchmarking $URL; evidence: $OUT"
hey "${HEY_ARGS[@]}" "$URL" > "$OUT/hey.txt" 2> "$OUT/hey.stderr.txt" &
LOAD_PID=$!
trap 'kill "$LOAD_PID" 2>/dev/null || true' EXIT
SAMPLE=0
while kill -0 "$LOAD_PID" 2>/dev/null; do
  bash "$SCRIPT_DIR/capture-evidence.sh" "during-$SAMPLE" "$OUT"
  SAMPLE=$((SAMPLE + 1))
  sleep 10
done
STATUS=0
wait "$LOAD_PID" || STATUS=$?
trap - EXIT
printf 'hey_exit=%s\n' "$STATUS" >> "$OUT/metadata.txt"
cat "$OUT/hey.txt"
bash "$SCRIPT_DIR/capture-evidence.sh" after "$OUT"
# Samples show recovery; no promise that scale-down finishes within this window.
ELAPSED=0
while [ "$ELAPSED" -lt "$RECOVERY_SECONDS" ]; do
  sleep 15
  ELAPSED=$((ELAPSED + 15))
  bash "$SCRIPT_DIR/capture-evidence.sh" "recovery-$ELAPSED" "$OUT"
done
date -u +finished_at=%Y-%m-%dT%H:%M:%SZ >> "$OUT/metadata.txt"
exit "$STATUS"
