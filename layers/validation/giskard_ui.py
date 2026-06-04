"""Serialize Giskard scan results for Streamlit (issues first, scan logs)."""
from __future__ import annotations

import json
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Plain-language hints for common Giskard detector / log messages (EM-friendly).
DETECTOR_HELP: dict[str, str] = {
    "LLMFaithfulnessDetector": (
        "Checks whether the model output stays faithful to the input context. "
        "Requires `litellm` + an LLM API key when enabled; otherwise it logs an error and skips."
    ),
    "LLMImplausibleOutputDetector": "Flags outputs that look implausible relative to the prompt.",
    "LLMHarmfulContentDetector": "Scans for harmful or unsafe content in generations.",
    "LLMPromptInjectionDetector": "Tests robustness to prompt-injection style inputs.",
    "LLMBasicSycophancyDetector": "Detects overly agreeable or sycophantic answers.",
}


def extract_scan_payload(scan_result: Any) -> dict[str, Any]:
    """Turn a Giskard ScanReport into JSON-safe UI payload."""
    issues_out: list[dict[str, Any]] = []
    for issue in getattr(scan_result, "issues", None) or []:
        issues_out.append(
            {
                "title": getattr(issue, "group_name", None)
                or getattr(issue, "name", None)
                or issue.__class__.__name__,
                "description": getattr(issue, "description", None) or str(issue),
                "level": getattr(issue, "level", None) or getattr(issue, "severity", "major"),
                "meta": getattr(issue, "meta", None),
            }
        )

    scan_logs: list[dict[str, str]] = []
    detectors = list(getattr(scan_result, "detectors_names", None) or [])
    try:
        raw = json.loads(scan_result.to_json())
        for name, block in raw.items():
            if not isinstance(block, dict):
                continue
            if block.get("error") or block.get("errors"):
                scan_logs.append(
                    {
                        "detector": name,
                        "level": "error",
                        "message": str(block.get("error") or block.get("errors")),
                        "help": DETECTOR_HELP.get(name, "Giskard detector raised an error during scan."),
                    }
                )
            elif block.get("issues") or block.get("findings"):
                scan_logs.append(
                    {
                        "detector": name,
                        "level": "warning",
                        "message": f"Findings: {block.get('issues') or block.get('findings')}",
                        "help": DETECTOR_HELP.get(name, ""),
                    }
                )
            else:
                scan_logs.append(
                    {
                        "detector": name,
                        "level": "info",
                        "message": "Completed — no issues recorded for this detector.",
                        "help": DETECTOR_HELP.get(name, ""),
                    }
                )
    except Exception as e:
        scan_logs.append(
            {
                "detector": "scan",
                "level": "error",
                "message": f"Could not parse scan JSON: {e}",
                "help": "",
            }
        )

    has_issues_fn = getattr(scan_result, "has_issues", None)
    has_issues = has_issues_fn() if callable(has_issues_fn) else bool(has_issues_fn)

    return {
        "has_issues": has_issues,
        "issue_count": len(issues_out),
        "issues": issues_out,
        "detectors_run": detectors,
        "scan_logs": scan_logs,
    }


def collect_findings(
    *,
    giskard_scan: dict[str, Any] | None = None,
    report_validation: dict[str, Any] | None = None,
    giskard_suite: dict[str, Any] | None = None,
    validation_issues: list[str] | None = None,
    ingestion_errors: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Merge all validation sources into one list for UI (shown first)."""
    findings: list[dict[str, Any]] = []

    for issue in (giskard_scan or {}).get("issues") or []:
        findings.append(
            {
                "source": "giskard.scan",
                "level": "critical",
                "title": issue.get("title", "Giskard issue"),
                "detail": issue.get("description", ""),
            }
        )

    for log in (giskard_scan or {}).get("scan_logs") or []:
        if log.get("level") == "error":
            findings.append(
                {
                    "source": "giskard.log",
                    "level": "warning",
                    "title": f"{log.get('detector', 'Detector')} — scan log error",
                    "detail": log.get("message", ""),
                }
            )

    for msg in (giskard_suite or {}).get("failures") or []:
        findings.append(
            {"source": "giskard.suite", "level": "critical", "title": "Suite check failed", "detail": msg}
        )

    for msg in (report_validation or {}).get("issues") or []:
        findings.append(
            {
                "source": "giskard.report",
                "level": "warning",
                "title": "RCA report validation",
                "detail": msg,
            }
        )

    for msg in validation_issues or []:
        findings.append(
            {
                "source": "trust",
                "level": "warning",
                "title": "Trust check",
                "detail": msg,
            }
        )

    for msg in ingestion_errors or []:
        findings.append(
            {
                "source": "ingestion",
                "level": "critical",
                "title": "Ingestion blocked",
                "detail": msg,
            }
        )

    return findings


GISKARD_ROLE = (
    "After AI Reasoning (Groq) produces the RCA, Giskard runs on this incident only "
    "(one giskard.scan, no extra Groq for predict). ORI also applies grounding rules "
    "against your pasted signals and ChromaDB context."
)


def _overlap_tokens(a: str, b: str) -> float:
    wa = {w.lower() for w in a.split() if len(w) > 3}
    wb = {w.lower() for w in b.split() if len(w) > 3}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), 1)


def build_grounding_audit(
    incident: Any,
    rca: Any,
    similar: list[Any],
    report_val: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Cite where RCA claims are grounded — for UI trust section."""
    signal_blob = "\n".join(incident.signals)
    if incident.description:
        signal_blob = f"{incident.description}\n{signal_blob}"
    if incident.deployment_notes:
        signal_blob = f"{signal_blob}\n{incident.deployment_notes}"

    evidence_rows: list[dict[str, Any]] = []
    for line in rca.evidence or []:
        score = _overlap_tokens(line, signal_blob)
        matched = "yes" if score >= 0.15 else ("weak" if score > 0 else "no")
        source = "your signals / description"
        if score < 0.15 and similar:
            for s in similar[:2]:
                if _overlap_tokens(line, f"{s.title} {s.description or ''}") >= 0.12:
                    matched = "partial (historical)"
                    source = f"ChromaDB [{s.incident_id}]"
                    break
        evidence_rows.append(
            {
                "claim": line[:200],
                "grounded": matched,
                "source": source,
                "overlap": round(score, 2),
            }
        )

    rc_score = _overlap_tokens(rca.probable_root_cause, signal_blob)
    sources_used: list[str] = ["Pasted signals and description"]
    if incident.deployment_notes:
        sources_used.append("Deployment notes")
    if similar:
        sources_used.append(
            "ChromaDB: " + ", ".join(f"{s.incident_id}" for s in similar[:3])
        )
    else:
        sources_used.append("ChromaDB: none matched above threshold")

    return {
        "root_cause_overlap": round(rc_score, 2),
        "root_cause_grounded": rc_score >= 0.08,
        "evidence_citations": evidence_rows,
        "input_sources": sources_used,
        "similar_incident_ids": [s.incident_id for s in similar],
        "claims_checked": (report_val or {}).get("claims_checked", []),
        "vector_context_used": (report_val or {}).get("vector_context_used", False),
    }


def build_outcome_explanation(
    out: dict[str, Any],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Human-readable success vs issues narrative for the UI."""
    outcome = out.get("outcome") or compute_outcome(findings, out.get("giskard_badge"))
    rv = out.get("giskard_report_validation") or {}
    scan = out.get("giskard_scan") or {}
    grounding = rv.get("label_alignment_score")
    vector_used = rv.get("vector_context_used")
    claims = rv.get("claims_checked") or []

    scan_ran = bool(out.get("giskard_live_scan", {}).get("enabled"))
    if outcome == "pass":
        reasons = []
        if scan_ran and scan:
            reasons.append("✅ giskard.scan on this incident found no detector issues.")
        elif scan_ran:
            reasons.append("✅ Giskard live scan completed (see report below).")
        reasons.extend([
            f"✅ Trust badge {out.get('giskard_badge', 'PASS')} — evidence and components align with pasted signals.",
            "✅ Grounding check: RCA claims cite your operational input.",
        ])
        if vector_used:
            reasons.append("✅ Vector store context was used to cross-check the narrative.")
        else:
            reasons.append("ℹ️ No similar incidents in ChromaDB; assessment used your pasted input only.")
        if claims:
            reasons.append(f"✅ Claims reviewed: {', '.join(claims)}.")
        return {
            "outcome": "pass",
            "headline": "✅ Low risk — trust & quality assessment passed",
            "summary": (
                "The RCA is grounded and cited against your signals (low hallucination risk). "
                "This is not a guarantee the root cause is correct — verify before production action."
            ),
            "reasons": reasons,
        }

    why: list[str] = [
        "🚨 Giskard or trust checks flagged one or more problems with the RCA report.",
    ]
    if out.get("giskard_badge") == "FAIL":
        why.append("🔴 FAIL — likely hallucinated components or critical grounding gap.")
    elif out.get("giskard_badge") == "FLAG":
        why.append("🟡 FLAG — partial grounding; some evidence or root cause text is weakly supported.")
    if scan.get("issue_count", 0) > 0:
        why.append(
            f"🔴 Giskard HTML report lists {scan['issue_count']} detector issue(s) — open the report below."
        )
    for f in findings[:5]:
        why.append(f"• [{f.get('source')}] {f.get('detail', f.get('title', ''))[:200]}")
    if len(findings) > 5:
        why.append(f"• … and {len(findings) - 5} more (see list below).")

    return {
        "outcome": "issues_detected",
        "headline": "🚨 Elevated risk — review before acting",
        "summary": (
            "The RCA was still generated with next action items, but trust checks flagged "
            "grounding or detector risk. PASS/FAIL does not prove correctness — use evidence "
            "and the Giskard report, then confirm with your runbooks."
        ),
        "reasons": why,
    }


def compute_outcome(findings: list[dict[str, Any]], badge: str | None = None) -> str:
    """
    pass — clean run
    issues_detected — Giskard/trust/ingestion flagged problems (show red in UI)
    """
    if any(f["level"] == "critical" for f in findings):
        return "issues_detected"
    if badge in ("FAIL", "FLAG"):
        return "issues_detected"
    if findings:
        return "issues_detected"
    return "pass"
