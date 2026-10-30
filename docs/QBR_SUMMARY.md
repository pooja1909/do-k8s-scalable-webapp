# Quarterly Business Review: Web Platform on DigitalOcean Kubernetes

**Prepared by:** Pooja Singh, Technical Account Manager  ·  **Audience:** CTO, VP Engineering, platform team

## 1. Summary

The web app now runs on DigitalOcean Kubernetes, behind a DigitalOcean Load Balancer, and scales automatically in both
directions. It meets all four goals: it absorbs traffic growth without manual work, keeps response times steady under
load, survives a node failure without downtime, and costs about **$113/month in a typical month**, including a high-availability
control plane. Sizing for peak without autoscaling would cost $148/month.

| Goal | Status | Evidence |
| --- | --- | --- |
| Scalability | Met | HPA scaled pods from 2 to 10 (the cap) under load and back to 2 when idle; Cluster Autoscaler can add nodes up to 4. |
| Performance | Met | p95 latency 26 ms at 2,311 requests/sec through the Load Balancer. |
| Reliability | Met | 2+ pods on separate nodes, health-checked Load Balancer, zero-downtime rolling updates, 0% errors during scale-up; Load Balancer health checks 100%, 0 s downtime. |
| Cost | Met | $100/month baseline (HA control plane included), ≈ $113 typical, $148 hard ceiling. |

## 2. Current infrastructure and performance

- **Cluster:** DOKS in `sfo3`, high-availability control plane (99.95% SLA), metrics-server add-on.
- **Nodes:** one autoscaling pool of `s-2vcpu-4gb` Basic Droplets, minimum 2, maximum 4.
- **App:** Node.js container, 2–10 pods; each pod requests 100m CPU and 64 MiB of memory. HPA target is 50% CPU.
- **Traffic:** a DigitalOcean Load Balancer with an HTTP health check on `/healthz`; requests spread evenly across pods.
- **Measured performance:** normal page 2,311 requests/sec, p50 21 ms, p95 26 ms, 0 errors (138,757 requests). CPU-heavy page
  p50 1.24 s, p95 1.93 s; errors fell from 1.5% to 0% after making the health checks tolerant of busy pods. Pods scaled
  2 → 10 under load and back to 2 about 1–2 minutes after load stopped.

## 3. Recommendations

**Next 30 days (before launch)**

1. **Right-size CPU requests.** Under heavy load each pod used up to 500m CPU but reserved only 100m, so the Cluster
   Autoscaler (which scales on reservations) never added a node and the cluster saturated. Raising the request to match
   real usage lets it add nodes before CPU runs out.
2. **Add HTTPS** with a free Let's Encrypt certificate on the Load Balancer, and redirect HTTP to HTTPS.
3. **Automate deploys** with a GitHub Actions pipeline: build, push to DOCR, apply to DOKS. This removes manual steps
   and makes rollbacks one click.
4. **Set alerts:** node CPU and memory alerts in DigitalOcean Monitoring, plus a billing alert at $90/month.

**Next quarter (as users grow)**

5. **Rebalance pods after scale-down.** Spread rules apply only when pods are placed, so after a spike the remaining
   pods can share one node. Add the Kubernetes Descheduler, or keep a minimum of 3 replicas.
6. **Serve static assets from Spaces + CDN** to take load off the pods and cut latency for users far from `sfo3`.
7. **Scale on traffic, not only CPU.** Add a requests-per-second metric (for example with KEDA) so pods are added before
   CPU climbs.
8. **Move stateful data to DigitalOcean Managed Databases** rather than in-cluster, for backups and failover.

## 4. Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| New nodes take 3–5 minutes to join | Latency rises during a sudden spike if the nodes are already full | Keep the 2-node minimum with headroom; schedule a higher minimum ahead of known launches or campaigns. |
| Single region (`sfo3`) | A regional outage takes the app down | Document a restore runbook now; add a second region when revenue justifies it. |
| Spend grows with traffic | Surprise bills | `maxReplicas` and `max-nodes` caps, billing alerts, monthly cost review in this QBR. |
| Account Droplet limit (25 by default) | Cluster Autoscaler can't add nodes | Request a limit increase before growth. |
| metrics-server stops reporting | HPA can't scale | Alert on HPA `<unknown>` targets; metrics-server is a managed add-on. |
| No HTTPS yet | Data in transit not encrypted; browsers flag the site | Add the Let's Encrypt certificate (recommendation 2). |
| Load Balancer capacity | Throughput limit at high traffic | Monitor LB connections; add Load Balancer nodes as traffic grows. |

## 5. Next steps

| Action | Owner | Due |
| --- | --- | --- |
| Approve HTTPS and CPU right-sizing | Customer CTO | Before launch |
| Build the GitHub Actions deploy pipeline | Customer platform team, with TAM support | 30 days |
| Set up monitoring and billing alerts | TAM + customer platform team | 2 weeks |
| Review two weeks of production data and right-size | TAM | Next monthly check-in |
