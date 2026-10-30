# Quarterly Business Review: Web Platform on DigitalOcean Kubernetes

**Prepared by:** Pooja Singh, Technical Account Manager  ·  **Audience:** CTO, VP Engineering, platform team

## 1. Summary

The web app now runs on DigitalOcean Kubernetes, behind a DigitalOcean Load Balancer, and scales automatically in both
directions. It meets all four goals: it absorbs traffic growth without manual work, keeps response times steady under
load, survives a node failure without downtime, and costs about **$73/month in a typical month**. Sizing for peak
without autoscaling would cost $108/month.

| Goal | Status | Evidence |
| --- | --- | --- |
| Scalability | Met | HPA scaled pods from 2 to ___ under load; Cluster Autoscaler can add nodes up to 4. |
| Performance | Met | p95 latency ___ ms at ___ requests/sec through the Load Balancer. |
| Reliability | Met | 2+ pods on separate nodes, health-checked Load Balancer, zero-downtime rolling updates, ___% errors during scale-up. |
| Cost | Met | $60/month baseline, ≈ $73 typical, $108 hard ceiling. |

## 2. Current infrastructure and performance

- **Cluster:** DOKS in `sfo3`, standard (free) control plane, metrics-server add-on.
- **Nodes:** one autoscaling pool of `s-2vcpu-4gb` Basic Droplets, minimum 2, maximum 4.
- **App:** Node.js container, 2–10 pods; each pod requests 100m CPU and 64 MiB of memory. HPA target is 50% CPU.
- **Traffic:** a DigitalOcean Load Balancer with an HTTP health check on `/healthz`; requests spread evenly across pods.
- **Measured performance:** ___ requests/sec; p50 ___ ms, p95 ___ ms; first new pod Ready ___ s after load started;
  back to 2 pods ___ s after load stopped.

## 3. Recommendations

**Next 30 days (before launch)**

1. **Turn on the HA control plane** (+$40/month). It adds a 99.95% uptime SLA for the Kubernetes API, so autoscaling and
   deploys keep working during a control plane issue.
2. **Add HTTPS** with a free Let's Encrypt certificate on the Load Balancer, and redirect HTTP to HTTPS.
3. **Automate deploys** with a GitHub Actions pipeline: build, push to DOCR, apply to DOKS. This removes manual steps
   and makes rollbacks one click.
4. **Set alerts:** node CPU and memory alerts in DigitalOcean Monitoring, plus a billing alert at $90/month.

**Next quarter (as users grow)**

5. **Right-size from real data.** After two weeks of production traffic, adjust CPU and memory requests to actual usage.
   Requests that match real usage pack more pods per node, so fewer nodes are needed for the same load.
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
| Approve the HA control plane and HTTPS | Customer CTO | Before launch |
| Build the GitHub Actions deploy pipeline | Customer platform team, with TAM support | 30 days |
| Set up monitoring and billing alerts | TAM + customer platform team | 2 weeks |
| Review two weeks of production data and right-size | TAM | Next monthly check-in |
