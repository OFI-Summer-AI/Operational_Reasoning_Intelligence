# Test case 4 — P4 informational

**Scenario:** Planned certificate rotation on an internal admin portal — no customer impact.

**Severity:** `P4` — Low / informational

## Inputs

Use `p4_informational.json`.

| Field | Value |
|-------|--------|
| **Title** | Planned certificate rotation — P4 |
| **Severity** | P4 |
| **Affected system** | admin-portal |
| **Description** | Scheduled rotation of TLS certificates on internal admin portal. No customer-facing impact expected. |
| **Deployment notes** | Change ticket CHG-8842 — Sunday 02:00 UTC window |
| **Signals** | INFO-level cert-manager and health-check lines only |

## Expected output (qualitative)

| Check | Expected |
|-------|----------|
| Ingestion | Pass |
| Groq RCA | Acknowledges **planned change**, low risk |
| Trust badge | **PASS** typical |
| Recommended actions | Verify dry-run, monitor window, rollback plan — not war-room escalation |
| Tone | Calm; no invented customer outage |
