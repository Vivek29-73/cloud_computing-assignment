# Load test, cost and SLO (measured on one laptop, single-node k3d)

Command (standard): `locust -f tools/locustfile.py --headless --users 4 --spawn-rate 4 --run-time 2m --host http://localhost:8080 --csv results/loadtest`
Deployment at the time: 2 replicas (command-parser, namespace app), model version v1, CPU limit 1 and memory limit 1 GiB per replica.

## Measured (from the Locust output)

| Metric | Value |
|---|---|
| Requests | 109 |
| Failures | 2 (1.83%): one HTTP 500, one HTTP 502 |
| Average / median latency | 4,367 ms / 4,500 ms |
| p95 / p99 latency | 7,900 ms / 17,000 ms |
| Min / max latency | 294 ms / 18,811 ms |
| Throughput | 0.94 requests/s |
| Successful requests per replica (X-Served-By) | 68 and 39 of 107 (63.6% and 36.4%) |
| Model version served (X-Model-Version) | v1: 107 of 107 |
| kubectl top pods (during the run) | TO FILL FROM YOUR OWN OUTPUT |

Assessment thresholds (error rate <= 1% and p95 <= 5,000 ms): **not met** in this run (1.83% and 7,900 ms).
Load balancing: each replica served more than 30% of successful requests (63.6% and 36.4%).

## Cost per 1,000 requests (rate_card.json: 3.50 INR per vCPU-hour, 0.45 INR per GiB-hour)

1. Cost of one replica per hour = 1 vCPU x 3.50 + 1 GiB x 0.45 = 3.95 INR
2. Hourly cost of all running replicas = 2 x 3.95 = 7.90 INR
3. Requests served per hour = 0.94 requests/s x 3,600 s = 3,384 requests
4. Cost per 1,000 requests = (7.90 / 3,384) x 1,000 = **2.33 INR** (2.3346)

Assumption: throughput is Locust's aggregated requests per second (successful and failed). Using only the 107 successful requests gives about 3,323 requests per hour and 2.38 INR.

## SLO and error budget

- SLO: 99% of requests succeed (HTTP 200 within 30 s).
- Window: one Locust run (2 minutes, 4 users, 109 requests).
- Error budget: 1% of 109 = 1.09 requests, so at most 1 failed request.
- Observed: 2 failures, which is a success rate of 107/109 = 98.17%.
- Budget used: 2 / 1.09 = 183%. **The SLO was not met in this run.**
