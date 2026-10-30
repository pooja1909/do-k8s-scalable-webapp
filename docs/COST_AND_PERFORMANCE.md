# Cost and Performance Analysis

DigitalOcean list prices as of October 2026. Check the
[DigitalOcean pricing page](https://www.digitalocean.com/pricing) before quoting a customer.

## Bill of materials

| Component | Choice | Unit price | Why this choice |
| --- | --- | --- | --- |
| Control plane | DOKS high-availability (HA) control plane | $40/month | Enabled on this cluster: replicated control plane with a 99.95% SLA, so scaling and deploys keep working during a control-plane issue. |
| Worker nodes | Basic Droplet `s-2vcpu-4gb`, autoscaling pool, 2–4 nodes | $24/month ($0.03571/hour) | Smallest size with room for system pods plus several app pods. Two nodes minimum so one node can fail without downtime. |
| Load Balancer | DigitalOcean regional Load Balancer, 1 node | $12/month | Created automatically by the `LoadBalancer` Service. One node handles this workload; add nodes as traffic grows. |
| Container registry | DOCR Starter | $0 | 1 repository, 500 MiB, enough for one ~50 MB image. Move to Basic ($5/month) for more repositories. |
| Outbound transfer | Pooled allowance included with the Droplets | $0.01/GiB above the allowance | No extra cost at demo traffic levels. |

## Monthly cost

| Scenario | Nodes | Calculation | Monthly cost |
| --- | --- | --- | --- |
| **Baseline (quiet periods)** | 2 | 2 × $24 + $40 HA + $12 LB | **$100** |
| **Typical month** (peak 6 h/day at 4 nodes) | 2–4 | $100 + (2 nodes × 6 h × 30 days × $0.03571) | **≈ $113** |
| **Ceiling** (4 nodes all month) | 4 | 4 × $24 + $40 HA + $12 LB | **$148** |
| Static sizing for peak (no autoscaling) | 4 | 4 × $24 + $40 HA + $12 LB | $148 |
| Without the HA control plane | — | Standard control plane is free | − $40 on every line |

**How this avoids waste:** sizing statically for peak costs $148 every month. With autoscaling, the customer pays about
$113 in a typical month, **about $35 (24%) less**, and $100 (32% less) in a quiet month. These figures match
DigitalOcean's own cluster estimate in the control panel ($88–$136/month, HA included), plus $12 for the Load Balancer. The extra capacity exists only
while traffic needs it. `maxReplicas: 10` and `max-nodes: 4` act as a hard spending cap, so a traffic spike or a bug
cannot run up an open-ended bill.

## Where waste is avoided

1. **Autoscaling in both directions.** The HPA removes pods when CPU drops. The Cluster Autoscaler then removes nodes
   that are no longer needed, and node billing stops.
2. **Small requests.** Each pod requests 100m CPU and 64 MiB of memory, which matches normal traffic, so pods pack
   densely onto nodes. Requests set too high force extra nodes. The heavy load test showed 100m is too low under
   sustained load (pods used up to 500m, so the Cluster Autoscaler never added a node); raising the request from
   production data is QBR recommendation 1.
3. **Small Basic nodes, not one large node.** Two `s-2vcpu-4gb` nodes ($48) cost the same as one `s-4vcpu-8gb` node
   ($48), but survive a node failure and scale in $24 steps instead of $48 steps.
4. **Free tiers where they fit:** the DOCR Starter registry. The HA control plane ($40) is a deliberate reliability
   choice; a dev or test cluster could use the free standard control plane instead.
5. **Clean teardown.** The teardown script deletes the Service first so the Load Balancer is removed. Orphaned Load
   Balancers and volumes are the most common surprise charge after a test.

## Options considered and rejected

| Option | Why not |
| --- | --- |
| One larger node (`s-4vcpu-8gb`) | Same price as two small nodes, but a single point of failure. |
| General Purpose nodes | Dedicated CPU starts at about $63/node/month. Not needed for this workload; revisit if CPU steal shows up under load. |
| No autoscaling, sized for peak | $148/month every month, about $35 more than a typical month with autoscaling. |

## Performance results (measured October 30, 2026)

Load generated with `hey` from a laptop in the Bay Area, 50 concurrent connections for 60 seconds, through the public
Load Balancer.

| Measurement | Result |
| --- | --- |
| Requests/sec, light endpoint (`/api/info`) | 2,311 |
| p50 / p95 / p99 latency, light endpoint | 21 / 26 / 40 ms |
| Errors, light endpoint | 0% (138,757 requests); the HPA added 6 pods during the test |
| p50 / p95 latency, CPU endpoint (`/work?ms=50`) | 1.24 / 1.93 s (queueing at full CPU) |
| Errors, CPU endpoint | 1.5% before the probe fix, 0% after |
| Pods at peak | 10 of 10, spread 5 per node |
| Back to 2 pods after load stopped | about 1–2 minutes |
| Load Balancer health checks / downtime | 100% healthy, 0 s downtime |

**What the heavy test taught us:** with a 1-second liveness timeout, busy Node.js pods were restarted as if they were
dead. Longer probe timeouts fixed it. At deliberate overload the cluster still saturated, because the Cluster
Autoscaler scales on CPU *requests* (100m) while real usage reached 500m per pod. Raising requests to match real usage is
the first QBR recommendation.

**Expected behavior:** latency on the light endpoint stays low and flat. Under the CPU-heavy load, latency rises until
new pods are Ready, then drops back as traffic spreads out. Pods return to 2 roughly 1–2 minutes after load stops,
because the scale-down window is 60 seconds for the demo.
