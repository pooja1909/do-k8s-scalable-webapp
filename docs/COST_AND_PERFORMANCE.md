# Cost and Performance Analysis

**Review date: October 30, 2026.** Prices are USD list-price inputs; projections exclude tax, discounts, bandwidth overages, and additional services. Performance observations are short demo tests, not a production SLO or availability measurement.

## 1. Infrastructure pricing

The deployment uses a **REGIONAL_NETWORK** Load Balancer with one node, at **$15/month**, verified by API and dashboard. Sources: [LB pricing](https://docs.digitalocean.com/products/networking/load-balancers/details/pricing/), [Droplet pricing](https://www.digitalocean.com/pricing/droplets), and [DOKS pricing](https://docs.digitalocean.com/products/kubernetes/details/pricing/).

| Component | Configuration | Monthly input |
| --- | --- | --- |
| Workers | Basic `s-2vcpu-4gb`, 2 vCPU / 4 GiB each; 2-4 nodes | $24 each; $0.03571/hour equivalent |
| Control plane | HA enabled; explicitly selected by creation script | $40 |
| Load Balancer | Regional network, one node | $15 |
| Registry | Starter tier assumption; one repository within free allowance | $0 |

HA was verified by API and screenshot. Its [99.95% SLA](https://www.digitalocean.com/sla/doks) covers the control plane only; it does not establish application availability. The registry model assumes usage stays within its free-tier allowance.

## 2. Illustrative monthly scenarios

| Scenario | Calculation | Infrastructure subtotal |
| --- | --- | --- |
| Baseline: two continuously running workers | 2 x $24 + $40 + $15 | **$103.00** |
| Assumed daily peak: two extra workers for 6 h/day, 30 days | $103 + 2 x 6 x 30 x $0.03571 | **$115.86** |
| Four workers continuously; static peak sizing comparison | 4 x $24 + $40 + $15 | **$151.00** |

The illustrative daily-peak scenario saves **$35.14, or 23.3%**, against $151 static peak sizing. No billing history or observed node scale-out supports this duty cycle: it is a planning assumption. Bundled worker plans have a monthly cap and per-second billing; the hourly equivalent is used for transparent estimation. Reconcile actual usage and rounding against the invoice.

The subtotal is a hard spending ceiling. Pod and node limits bound configured capacity; bandwidth, additional LB nodes, storage, taxes, other services, and other account resources can increase the bill. Recommend a **$120 billing alert** aligned with the agreed account budget. An alert does not stop spending.

<!-- PAGEBREAK -->

## 3. Endpoint benchmark evidence

Both tests used `hey -z 60s -c 50 -disable-keepalive` from the same laptop through the public Load Balancer on October 30, 2026 (PDT), running release **1.0.2**. Each began with **two ready replicas and an idle HPA**, without internal load-generator traffic. Raw outputs and timestamped before/during/after/recovery snapshots are in `evidence/final/light/` and `evidence/final/work/`.

| Measurement | Light: `/api/info` | CPU-heavy: `/work?ms=50` |
| --- | --- | --- |
| Completed duration | 71.7956 seconds | 62.9169 seconds |
| Requests/second | 201.20 | 36.87 |
| p50 / p95 / p99 | 168.6 / 389.7 / 507.3 ms | 797.2 / 3,206.0 / 3,687.9 ms |
| HTTP results | 14,443 responses, all 200 | 2,299 responses, all 200 |
| Reported request errors | 2 timeouts / 14,445 attempts (0.014%) | 21 timeouts / 2,320 attempts (0.91%) |
| Starting replicas | 2 | 2 |
| Replica response, including recovery | 2 to 5, then back to 2 | 2 to 10, then back to 2 |
| Observed worker nodes | 2 throughout | 2 throughout |

The endpoints model different workloads: `/api/info` returns small JSON, while `/work?ms=50` deliberately consumes CPU in 5-ms chunks, yielding to I/O between chunks. Results include network latency and the autoscaling ramp. Fresh TCP connections let new pods receive new traffic. The 60-second setting controls request generation; completion can extend the reported duration. Latency percentiles describe completed responses; errors are listed separately. These are demo measurements, not production SLO validation. Node autoscaling is **configured, not exercised**.

A separate **keep-alive CPU stress test** (`persistent-work/`) recorded **1,289 HTTP 200 responses and one timeout**: 1/1,290 attempts, or **0.078%**. It ran for 77.1167 seconds including completion, at 16.73 requests/second; p95 was **3,327.6 ms** and p99 **9,126.0 ms**. Sampled pods remained ready with no restarts. The fresh-connection CPU test also had 21 timeouts (0.91% of attempts). Neither CPU test establishes a production latency or error SLO. The differing connection modes are not directly comparable. Uneven pod CPU is consistent with connection concentration, but the client-observed timeouts were not isolated to a specific application, client/network, or platform cause. This result is retained as a production-sizing risk.

The separate reliability checks recorded **485/485** HTTP 200 samples during deployment and **361/361** during voluntary pod recovery. Two ready replicas were observed **7.61 seconds** after the pod-eviction action started. The reliability section explains sampling, scope, and limitations; no application-uptime percentage or sudden-node-failure result is claimed.

<!-- PAGEBREAK -->

## 4. Why CPU pressure did not trigger more nodes

Each app pod requests **100m** and is limited to **500m**. The HPA's 50% utilization target is **50m per pod**, not 50% of a worker CPU or of the container limit. Ten pods request only **1 CPU** in total, yet their limits allow up to **5 CPUs** across the two workers' **4 nominal vCPUs**, before system reservations. This explains how the scheduler can consider pods to fit while actual CPU pressure is high.

The [Cluster Autoscaler](https://docs.digitalocean.com/products/kubernetes/how-to/autoscale/) responds to unschedulable pods and scheduling constraints; high observed CPU alone is not a scale-out trigger. Node count remained at two throughout the measured tests; successful node scale-out is not claimed.

Right-size requests and retune HPA **together**, then rerun a controlled test from a documented baseline. For example, changing 100m to 250m while keeping 50% changes the effective target from 50m to 125m. Preserving a 50m target would require 20%, but neither 250m nor 20% is a production recommendation without measurement. Record throttling, CPU demand, latency/errors, pending-pod reasons, scale-out time, and recovery before selecting values. Do not increase the CPU request in isolation and claim improved behavior.

## 5. Availability and cost tradeoffs

Two smaller nodes offer more placement options than a single larger node, but failover depends on placement and available capacity. The final baseline has one ready app pod on each worker; placement must be checked after every scale-down. Topology spread applies at scheduling time; increasing the minimum to three replicas does not guarantee balanced survivors after scale-down. A PDB constrains voluntary evictions and cannot prevent involuntary node loss.

Keep the Basic worker plan for the demo and evaluate sustained CPU needs with representative traffic before choosing dedicated CPU. Keep HTTPS, deployment automation, CDN, and managed databases on the prioritized roadmap. Use representative traffic, recovery exercises, and billing history to validate production performance, availability, and savings.
