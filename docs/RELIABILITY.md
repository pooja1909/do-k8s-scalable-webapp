# Reliability Validation

**Measured October 30, 2026, through the public Load Balancer.** The application has two baseline replicas, readiness/liveness probes, a 30-second termination grace period, graceful connection draining, a rolling strategy with zero unavailable replicas, and a PDB requiring one available replica. Scheduling spreads pods across workers. CPU work yields to I/O between 5-ms chunks so probes can respond under concurrent work.

## Timed deployment and recovery checks

| Measurement | Rolling deployment | Voluntary pod recovery |
| --- | --- | --- |
| HTTP sampling window (UTC) | 22:51:47.100-22:52:37.409 | 22:52:58.957-22:53:36.491 |
| Samples / HTTP 200 / errors | 485 / 485 / 0 | 361 / 361 / 0 |
| HTTP p95 / maximum latency | 107.4 / 168.2 ms | 111.1 / 120.8 ms |
| Minimum sampled available replicas | 2 | 1 |
| Action start to two ready replicas observed | 20.37 seconds | 7.61 seconds |
| Placement after the action | One ready replica per worker | One ready replica per worker |

The rollout deployed release **1.0.2** and preserved the HPA's desired count of two throughout sampled observations. Its saved apply configuration contains no replica count. The recovery check evicted one app pod through the `policy/v1` Eviction API with a UID precondition and PDB enforcement, then observed its replacement become ready. The worker remained online. Public responses came from pods on both workers in each test.

## Reproducibility and interpretation

`scripts/reliability-check.py` verifies the cluster identity and requires two healthy replicas, a disruption allowance, and no internal load generator. It records ten seconds of baseline traffic, performs the action, waits for recovery, then records twenty seconds of additional traffic. HTTP sampling is sequential at up to ten requests/second, with a three-second request timeout. Cluster state is sampled approximately every two seconds.

Raw HTTP, pod, HPA, PDB, action, and timing logs are under `evidence/final/rollout/` and `evidence/final/pod-recovery/`. These deployment/recovery windows had **no observed request errors**; the performance section separately reports the CPU stress-test timeouts. Gaps between samples are unmeasured; these short tests do not establish a long-term uptime percentage, production SLO, or recovery from sudden worker or regional failure.

## Operational follow-through

After autoscaling, check actual placement. Topology spread governs scheduling and does not rebalance survivors after scale-down. At an idle baseline, a monitored PDB-respecting eviction can restore distribution when both workers are eligible; verify the result. For production, alert on missing ready replicas and concentrated placement, and evaluate automated rebalancing under an explicit eviction policy.

Agree customer recovery and latency/error targets, then test abrupt worker loss, sustained load, and rollback in a controlled window. HA control-plane configuration and voluntary-disruption protection support availability; application failure tolerance still requires workload-specific testing.
