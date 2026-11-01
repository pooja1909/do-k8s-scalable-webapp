# Quarterly Business Review

**Web platform on DigitalOcean Kubernetes**

**Prepared by:** Pooja Singh, Senior Technical Account Manager

**Audience:** CTO, VP Engineering, platform team | **Review:** November 2, 2026

## Customer outcome and current infrastructure

The deployed Node.js application demonstrates public load distribution, CPU-driven pod autoscaling, a monitored rolling deployment, and recovery from a voluntary pod eviction. The environment uses DOKS in **sfo3**, an HA control plane, two **2-vCPU / 4-GiB** Basic workers, and a **regional network Load Balancer**. HPA bounds are **2-10 pods**; the node pool is configured for **2-4 workers**. Release **1.0.2** is live and its source hashes match the submitted code.

| Customer goal | Measured position |
| --- | --- |
| Scalability | Both endpoint tests began with two ready replicas and an idle HPA. Light scaled 2 to 5 to 2; CPU scaled 2 to 10 to 2, including recovery. Workers stayed at two; node scale-out was not exercised. |
| Performance | Light endpoint: p95 389.7 ms at 201.20 requests/sec, with two timeouts (0.014%). CPU-heavy endpoint: p95 3,206.0 ms at 36.87 requests/sec. Both used 50 concurrent connections for 60 seconds. The CPU test had 21 timeouts in 2,320 attempts (0.91%). |
| Reliability | Rollout: 485/485 sampled HTTP 200 responses. Pod recovery: 361/361 HTTP 200 responses; two ready replicas observed after 7.61 seconds. Final baseline has one ready replica per worker. |
| Cost | Modeled $103 baseline, $115.86 with two extra workers for an assumed 6 hours/day, and $151 for four continuously running workers. These are infrastructure projections. |

## Business interpretation

The light endpoint's p95 was below 0.4 seconds, but timeouts occurred in both endpoint tests. CPU-heavy requests reached p95 3.21 seconds with a 0.91% timeout rate, indicating a risk of slow or failed customer requests as demand grows. Automatic pod scaling responded to demand, but adding worker capacity remains untested. Before production launch, tune capacity and autoscaling together and validate agreed response-time and error targets with representative customer traffic.

The additional test with persistent connections recorded one timeout in 1,290 attempts (0.078%), with p95 3.33 seconds. Pods stayed ready in sampled observations, but readiness alone does not establish acceptable customer response times. Validate the connection patterns customers will actually use.

The network Load Balancer costs **$15/month**. The illustrative daily-peak scenario saves **$35.14 (23.3%)** against static four-worker sizing; the assumed duty cycle is not measured billing history. HA costs $40/month, and its 99.95% SLA covers the control plane. Short reliability checks establish observed outcomes within their sampling windows, not a long-term application uptime percentage.

<!-- PAGEBREAK -->

## Prioritized customer action plan

| When / owner | Action and acceptance evidence |
| --- | --- |
| Before production launch / platform + TAM | Agree response-time, error-rate, and recovery objectives. Test representative traffic and sustained CPU load; tune capacity and autoscaling together. Demonstrate that capacity arrives in time to meet the agreed targets and record the cost impact. |
| Before production launch / platform | Exercise abrupt worker loss and rollback with timed HTTP monitoring. Confirm placement and headroom after recovery; compare measured recovery time with the agreed objective. |
| Before production launch / TAM + platform | Configure and test latency, error, readiness, HPA-metrics, and placement alerts. Confirm alert owners and response procedures. Agree the account budget and configure a $120 billing alert if appropriate. |
| Before production launch / platform | Enable HTTPS with TLS termination at an ingress/app compatible with the network LB. Verify the certificate and redirect public HTTP traffic to HTTPS. |
| Within 30 days / platform | Add CI/CD with immutable images, automated checks, and tested rollback. |
| Next quarter / CTO + platform | Review two weeks of workload and billing data. Evaluate dedicated CPU, request-rate scaling, CDN for static assets, and Managed Databases when persistent data is introduced. |

## Risks and mitigations

| Risk | Mitigation / decision |
| --- | --- |
| Uneven pod placement after scale-down | Inspect placement; use monitored PDB-respecting pod replacement when needed. Evaluate automated rebalancing with an eviction policy. |
| CPU saturation and slow capacity arrival | Maintain measured headroom and tune requests/HPA together. Lengthen and validate the 60-second demo scale-down window for production traffic. |
| Single region and untested abrupt worker loss | Define recovery objectives and test the failure runbook. Evaluate a second region when business requirements justify it. |
| Spending above the modeled subtotal | Review transfer, LB size, storage, and other account services. Capacity bounds and billing alerts do not cap spending. |
| Overinterpreting short reliability tests | PDB covers voluntary evictions. Require sustained monitoring and abrupt-failure tests before adopting an application availability target. |

**Next customer check-in:** confirm performance and recovery objectives, account budget, and action owners. Review raw evidence together and prioritize work by customer impact. HTTPS and essential monitoring are production launch prerequisites. CI/CD, CDN, and persistent storage remain planned capabilities.
