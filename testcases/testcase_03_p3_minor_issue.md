# Test case 3 — P3 minor issue

**Scenario:** Stale catalog cache — some users see old prices; core checkout still works.

**Severity:** `P3` — Medium

## Inputs

Use `p3_minor_issue.json`.

| Field | Value |
|-------|--------|
| **Title** | Stale cache on product catalog — P3 |
| **Severity** | P3 |
| **Affected system** | catalog-cache |
| **Description** | Some product pages show outdated prices for ~15 minutes after catalog updates. Core purchase flow unaffected. |
| **Signals** | TTL miss rate elevated, refresh job skipped partitions, cache age alert |

## Expected output (qualitative)

| Check | Expected |
|-------|----------|
| Ingestion | Pass |
| Groq RCA | **Cache TTL / refresh job** — limited blast radius |
| Trust badge | Usually **PASS** |
| Recommended actions | Invalidate cache, fix refresh job, tune TTL — not emergency rollback of entire platform |
| Severity framing | RCA should **not** read like a P1 outage |
