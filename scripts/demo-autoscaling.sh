#!/usr/bin/env bash
# Demo 2: generate load, watch the HPA scale pods up, then stop the load and watch it scale down.
#   ./scripts/demo-autoscaling.sh start   # start load (2 generators)
#   ./scripts/demo-autoscaling.sh more    # heavier load (4 generators)
#   ./scripts/demo-autoscaling.sh watch   # live view of HPA, pods, and CPU
#   ./scripts/demo-autoscaling.sh stop    # stop load; pods scale back to 2 in ~1-2 minutes
set -uo pipefail   # no -e: keep watching through a brief API hiccup
K8S="$(dirname "$0")/../k8s"

case "${1:-watch}" in
  start)
    kubectl apply -f "$K8S/load-generator.yaml"
    echo "Load started. Run: $0 watch"
    ;;
  more)
    kubectl -n web-app scale deployment/load-generator --replicas=4
    ;;
  stop)
    kubectl delete -f "$K8S/load-generator.yaml" --ignore-not-found
    echo "Load stopped. Watch the HPA scale back down: $0 watch"
    ;;
  watch)
    while true; do
      clear
      date
      echo "--- HPA (target 50% CPU) ---"
      kubectl -n web-app get hpa web-app
      echo ""
      echo "--- Pod CPU / memory ---"
      kubectl -n web-app top pods -l app=web-app 2>/dev/null || echo "(metrics warming up)"
      echo ""
      echo "--- Pods by node ---"
      kubectl -n web-app get pods -l app=web-app --no-headers \
        -o custom-columns='POD:.metadata.name,STATUS:.status.phase,RESTARTS:.status.containerStatuses[0].restartCount,NODE:.spec.nodeName'
      echo ""
      echo "--- Nodes ---"
      kubectl get nodes --no-headers | awk '{print $1, $2}' | column -t
      sleep 5
    done
    ;;
  *)
    echo "usage: $0 {start|more|watch|stop}"; exit 1
    ;;
esac
