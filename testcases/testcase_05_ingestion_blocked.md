# Test case 5 — Ingestion blocked (invalid input)

**Scenario:** Operator files a P1 ticket with a title but **no description and no signals** — pipeline must stop before Groq.

**Severity:** Label says P1, but input is **invalid** for analysis.

## Inputs

Use `ingestion_blocked.json`.

| Field | Value |
|-------|--------|
| **Title** | Unknown outage — missing signals |
| **Severity** | P1 |
| **Affected system** | unknown |
| **Description** | *(empty)* |
| **Signals** | *(none)* |

## Expected output

| Check | Expected |
|-------|----------|
| Ingestion QA | **Fail** — error about missing operational signals |
| Groq | **Not called** |
| UI | Red “Could not process incident” (or equivalent) |
| Trust / RCA | None |

Use this to prove the **ingestion gate** works in demos.
