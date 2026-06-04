"""All prompt templates for the reasoning layer. No prompts live outside this file."""

SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) and incident analyst with \
deep knowledge of distributed systems, databases, networking, and deployment pipelines.

Your role is to analyse operational incidents: correlate signals, identify root causes, \
and recommend concrete remediation steps.

Rules:
- Only cite evidence that appears verbatim or paraphrased from the provided input signals.
- Never invent system names, component names, or metrics not present in the input.
- Express confidence honestly — if signals are ambiguous, say so in the confidence score.
- Keep evidence items as direct quotes or close paraphrases from the input signals.
- next_steps must be actionable and specific, not generic advice."""


CORRELATION_PROMPT = """## Incident Details

**Title:** {title}
**Severity:** {severity}
**Affected System:** {affected_system}

**Description:**
{description}

**Raw Signals (alerts, logs, events):**
{signals}

**Deployment Notes:**
{deployment_notes}

---

## Similar Historical Incidents

{similar_incidents}

---

## Task — Step 1: Signal Correlation

Analyse the signals above. Identify:
1. Which signals are causally related vs. symptomatic
2. The timeline of events (if timestamps are present)
3. Whether the deployment notes are relevant to the failure
4. Patterns matching the similar historical incidents

Write a concise correlation analysis (3–5 sentences)."""


RCA_PROMPT = """## Correlation Analysis

{correlation_result}

---

## Task — Step 2: Root Cause Analysis

Based on the correlation analysis and original signals, generate a root cause analysis.

Return ONLY a valid JSON object with this exact schema:
{{
  "probable_root_cause": "<one clear sentence describing the root cause>",
  "confidence": <integer 0-100>,
  "affected_components": ["<component1>", "<component2>"],
  "evidence": [
    "<direct quote or close paraphrase from input signals>",
    "<another evidence item>"
  ],
  "next_steps": [
    "<specific actionable step 1>",
    "<specific actionable step 2>",
    "<specific actionable step 3>"
  ],
  "similar_incident_ids": ["<id1>", "<id2>"]
}}

Constraints:
- Every item in `evidence` MUST reference words present in the input signals.
- Every item in `affected_components` MUST appear in the signals or deployment notes.
- `confidence` should reflect actual signal quality: missing signals → lower confidence.
- Return ONLY the JSON object. No markdown fences, no explanation."""


UNIFIED_RCA_PROMPT = """## Incident Details

**Title:** {title}
**Severity:** {severity}
**Affected System:** {affected_system}

**Description:**
{description}

**Raw Signals (alerts, logs, events):**
{signals}

**Deployment Notes:**
{deployment_notes}

---

## Similar Historical Incidents

{similar_incidents}

---

## Task — Correlate signals and produce RCA (single response)

1. Correlate the signals (causal vs symptomatic, timeline, deployment relevance, historical patterns).
2. Produce a root cause analysis grounded in the signals above.

Return ONLY a valid JSON object with this exact schema:
{{
  "correlation_summary": "<3-5 sentences: how signals relate>",
  "probable_root_cause": "<one clear sentence describing the root cause>",
  "confidence": <integer 0-100>,
  "affected_components": ["<component1>", "<component2>"],
  "evidence": [
    "<direct quote or close paraphrase from input signals>",
    "<another evidence item>"
  ],
  "next_steps": [
    "<specific actionable step 1>",
    "<specific actionable step 2>",
    "<specific actionable step 3>"
  ],
  "similar_incident_ids": ["<id1>", "<id2>"]
}}

Constraints:
- Every item in `evidence` MUST reference words present in the input signals.
- Every item in `affected_components` MUST appear in the signals or deployment notes.
- `confidence` should reflect actual signal quality: missing signals → lower confidence.
- Return ONLY the JSON object. No markdown fences, no explanation."""


SYNTHETIC_INCIDENT_PROMPT = """Generate {n} realistic enterprise IT incidents as a JSON array.
Each element must have these fields:
- incident_id: "SYN-<3-digit-number>"
- title: short descriptive title
- description: 2-3 sentences
- severity: P1/P2/P3/P4
- affected_system: service or component name
- signals: list of 3 realistic log/alert lines
- deployment_notes: recent deployment description or null
- source_dataset: "synthetic"
- true_root_cause: specific root cause

Mix: database, network, memory, deployment, and dependency failure causes.
Return ONLY the JSON array."""
