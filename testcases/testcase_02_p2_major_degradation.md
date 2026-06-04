# Test case 2 — P2 major degradation

**Scenario:** Checkout is painfully slow and error rate is elevated, but payments still complete — not a full outage.

**Severity:** `P2` — High

## Inputs

Use `p2_major_degradation.json` or paste:

| Field | Value |
|-------|--------|
| **Title** | Checkout API elevated latency — P2 |
| **Severity** | P2 |
| **Affected system** | checkout-api |
| **Description** | Checkout completion time increased from ~400ms to 3–8s since 09:10 UTC. Payments still succeeding but cart abandonment rising. |
| **Deployment notes** | fraud-scoring-rules v1.9.2 rolled out 08:45 UTC |
| **Signals** | High p99 latency, fraud-scoring timeouts, 12% error rate, 2/8 pods unhealthy |

## Expected output (qualitative)

| Check | Expected |
|-------|----------|
| Ingestion | Pass |
| Groq RCA | Points to **latency / downstream dependency** (e.g. fraud-scoring), not “total outage” |
| Trust badge | **PASS** or **FLAG** |
| Recommended actions | Scale pods, rollback or tune fraud-scoring, investigate timeouts |
| Tone | Urgent but not “revenue stopped” level |
