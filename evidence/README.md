# Evidence Index

**Captured October 30, 2026 (PDT); raw timestamps use UTC.** Deployed release **1.0.2** is served through the public Load Balancer. `final/image-verification.txt` records Node 22.23.4, the non-root user, and source hashes matching the repository.

| Evidence | Location and scope |
| --- | --- |
| Endpoint benchmarks | `final/light/hey.txt` and `final/work/hey.txt`: fresh-connection tests, 50 workers, 60-second request window, two-pod baseline. Full results, including timeouts, appear in the performance section. |
| Keep-alive CPU stress | `final/persistent-work/`: 1,289 HTTP 200 responses, one timeout (0.078% of attempts), p95 3,327.6 ms.  |
| Scaling and recovery | Each benchmark has before/during/after/recovery snapshots. `final/*placement-recovery/` records controlled redistribution after scale-down. Workers stayed at two. |
| Rolling deployment | `final/rollout/`: 485/485 HTTP 200 samples, zero observed request errors, minimum sampled available replicas two, desired replicas preserved at two. |
| Pod recovery | `final/pod-recovery/`: one PDB-respecting voluntary eviction, 361/361 HTTP 200 samples, two ready replicas observed 7.61 seconds after action start. |
| Final cluster state | `final/baseline/`: one ready app replica per worker; HA true; DOKS 1.37.0-do.2; doctl 2.1.0; kubectl v1.36.1. |
| Effective LB settings | `final/baseline/load-balancer.json`: regional network, one node, managed HTTP health checks on 10256 at `/healthz`, distinct from the app on 8080. |
| Dashboard screenshots | `screenshots/`: HA, node autoscaling, LB type/cost, and health checks. Capture times are in `captures.txt`. |
| Regression checks | `local/node24-tests.txt` and `local/docker-node22-tests.txt`: seven passing test cases each. `local/script-safety-tests.txt`: seven passing safety tests with mocked cloud commands. |
| Release verification | `final/release.json` and `final/live-smoke.json`: image digest/source hashes and live endpoint checks. `local/validation-summary.txt`: shell, Python, YAML, and manifest relationships. |

`scripts/summarize-evidence.py` derives `final/summary.json`. Snapshot command logs preserve timestamps and exit statuses; pod JSON records image digests. Reliability logs contain every HTTP sample and sampled cluster state. Four optional API captures in light `recovery-30` timed out; stderr is retained. Recovery-folder numbers count sleep intervals, not wall time.

## Evidence boundaries

The rollout and voluntary pod-recovery windows had no observed request errors. Sampling gaps, long-term uptime, sudden worker loss, regional failure, and node autoscaling remain unmeasured. The cost model is illustrative, with no invoice validating the assumed extra-node duty cycle. 
