# Test case 1 — P1 critical outage

**Scenario:** Major production failure — customer-facing dashboard unavailable, clear error storm after a deploy.

**Severity:** `P1` — Critical (see sidebar in UI for definitions)

## Inputs

Copy into the UI or use `p1_critical_outage.json`.

| Field | Value |
|-------|--------|
| **Title** | Revenue Dashboard Unavailable — P1 |
| **Severity** | P1 |
| **Affected system** | revenue-dashboard |
| **Description** | Revenue dashboard failing to load for all users since 14:32 UTC. Multiple teams reporting inability to access real-time metrics. |
| **Deployment notes** | revenue-service v2.8.4 deployed at 14:28 UTC. Updated connection pool configuration. |
| **Signals** | See JSON file (gateway timeouts, pool exhausted, error rate 94%) |

## Expected output (qualitative)

| Check | Expected |
|-------|----------|
| Ingestion | Pass — rich signals + description |
| Groq RCA | Probable root cause tied to **deploy / connection pool / database** |
| Trust badge | Usually **PASS** or **FLAG** if evidence is thin |
| Outcome | **pass** or **issues_detected** only if grounding flags weak claims |
| Similar incidents | >0 if ChromaDB is seeded |

**Example root cause theme:** Misconfigured connection pool or DB exhaustion after v2.8.4 deploy.
