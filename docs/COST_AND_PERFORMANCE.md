# Cost and Performance Analysis

DigitalOcean list prices as of October 2026. Check the
[DigitalOcean pricing page](https://www.digitalocean.com/pricing) before quoting a customer.

## Bill of materials

| Component | Choice | Unit price | Why this choice |
| --- | --- | --- | --- |
| Control plane | DOKS standard | $0 | Free and managed. Use the HA control plane ($40/month, 99.95% SLA) for production. |
| Worker nodes | Basic Droplet `s-2vcpu-4gb`, autoscaling pool, 2–4 nodes | $24/month ($0.03571/hour) | Smallest size with room for system pods plus several app pods. Two nodes minimum so one node can fail without downtime. |
| Load Balancer | DigitalOcean regional Load Balancer, 1 node | $12/month | Created automatically by the `LoadBalancer` Service. One node handles this workload; add nodes as traffic grows. |
| Container registry | DOCR Starter | $0 | 1 repository, 500 MiB, enough for one ~50 MB image. Move to Basic ($5/month) for more repositories. |
| Outbound transfer | Pooled allowance included with the Droplets | $0.01/GiB above the allowance | No extra cost at demo traffic levels. |

## Monthly cost

| Scenario | Nodes | Calculation | Monthly cost |
| --- | --- | --- | --- |
| **Baseline (quiet periods)** | 2 | 2 × $24 + $12 LB | **$60** |
| **Typical month** (peak 6 h/day at 4 nodes) | 2–4 | $60 + (2 nodes × 6 h × 30 days × $0.03571) | **≈ $73** |
| **Ceiling** (4 nodes all month) | 4 | 4 × $24 + $12 LB | **$108** |
| Static sizing for peak (no autoscaling) | 4 | 4 × $24 + $12 LB | $108 |
| Production add-on | — | HA control plane | + $40 |

**How this avoids waste:** sizing statically for peak costs $108 every month. With autoscaling, the customer pays about
$73 in a typical month, **about $35 (32%) less**, and $60 (44% less) in a quiet month. The extra capacity exists only
while traffic needs it. `maxReplicas: 10` and `max-nodes: 4` act as a hard spending cap, so a traffic spike or a bug
cannot run up an open-ended bill.

## Where waste is avoided

1. **Autoscaling in both directions.** The HPA removes pods when CPU drops. The Cluster Autoscaler then removes nodes
   that are no longer needed, and node billing stops.
2. **Right-sized requests.** Each pod requests 100m CPU and 64 MiB of memory, close to what the app uses, so pods pack
   densely onto nodes. Requests that are set too high force extra nodes; requests that are too low cause noisy-neighbor
   slowdowns.
3. **Small Basic nodes, not one large node.** Two `s-2vcpu-4gb` nodes ($48) cost the same as one `s-4vcpu-8gb` node
   ($48), but survive a node failure and scale in $24 steps instead of $48 steps.
4. **Free tiers where they fit:** the standard control plane and the DOCR Starter registry.
5. **Clean teardown.** The teardown script deletes the Service first so the Load Balancer is removed. Orphaned Load
   Balancers and volumes are the most common surprise charge after a test.

## Options considered and rejected

| Option | Why not |
| --- | --- |
| One larger node (`s-4vcpu-8gb`) | Same price as two small nodes, but a single point of failure. |
| General Purpose nodes | Dedicated CPU starts at about $63/node/month. Not needed for this workload; revisit if CPU steal shows up under load. |
| No autoscaling, sized for peak | $108/month every month, about $35 more than a typical month with autoscaling. |

## Performance results (fill in from your run)

Run `./scripts/benchmark.sh` and `./scripts/benchmark.sh work`, and record what you see while the autoscaling demo runs.

| Measurement | Result | How measured |
| --- | --- | --- |
| Requests/sec, light endpoint (`/api/info`) | ___ | `hey -z 60s -c 50` through the Load Balancer |
| p50 / p95 / p99 latency, light endpoint | ___ / ___ / ___ ms | `hey` latency distribution |
| p50 / p95 latency, CPU endpoint (`/work?ms=50`) | ___ / ___ ms | `hey -z 60s -c 50` |
| Error rate during scale-up | ___% | `hey` status code distribution |
| Time from load start to first new pod Ready | ___ s | `demo-autoscaling.sh watch` |
| Pods at peak | ___ of 10 | `kubectl -n web-app get hpa` |
| Time from load stop back to 2 pods | ___ s | `demo-autoscaling.sh watch` |
| New node added? Time to Ready | ___ / ___ min | `kubectl get nodes -w` |
| Requests per pod in LB demo | ___ | `demo-load-balancing.sh` |

**Expected behavior:** latency on the light endpoint stays low and flat. Under the CPU-heavy load, latency rises until
new pods are Ready, then drops back as traffic spreads out. Pods return to 2 roughly 1–2 minutes after load stops,
because the scale-down window is 60 seconds for the demo.
