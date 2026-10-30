#!/usr/bin/env bash
# Measures response time and throughput through the public Load Balancer using `hey`.
# Install hey:  brew install hey   (macOS)   or   go install github.com/rakyll/hey@latest
# Usage:
#   ./scripts/benchmark.sh            # 60s test, 50 concurrent users, light page
#   ./scripts/benchmark.sh work       # 60s test hitting the CPU-heavy /work endpoint
# Copy the "Summary" and "Latency distribution" numbers into docs/COST_AND_PERFORMANCE.md.
set -euo pipefail
IP=$(kubectl -n web-app get svc web-app -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

if [ "${1:-}" = "work" ]; then
  URL="http://$IP/work?ms=50"
else
  URL="http://$IP/api/info"
fi

echo "Benchmarking $URL for 60s with 50 concurrent connections..."
hey -z 60s -c 50 "$URL"
