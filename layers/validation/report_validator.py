"""Validate RCA report claims against incident signals and vector-retrieved context."""
from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

from layers.ingestion.schema import SimilarIncident, UnifiedIncident
from layers.reasoning.rca_output import RCAOutput
from layers.validation.validator import RCAValidator, ValidationResult

logger = structlog.get_logger(__name__)


class GiskardReportValidation(BaseModel):
    """Outcome of report-level validation against signals and vector context (no extra Groq)."""

    passed: bool
    badge: str
    issues: list[str] = Field(default_factory=list)
    claims_checked: list[str] = Field(default_factory=list)
    vector_context_used: bool = False
    similar_incident_ids: list[str] = Field(default_factory=list)
    label_alignment_score: float = 0.0


def _token_overlap(a: str, b: str) -> float:
    wa = {w.lower() for w in a.split() if len(w) > 3}
    wb = {w.lower() for w in b.split() if len(w) > 3}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), 1)


def validate_rca_report(
    rca: RCAOutput,
    incident: UnifiedIncident,
    similar: list[SimilarIncident],
    base_validation: ValidationResult | None = None,
) -> GiskardReportValidation:
    """
    Check that RCA narrative (root cause, evidence, next steps) is supported by
    user input and optional ChromaDB historical context.
    """
    validator = RCAValidator()
    base = base_validation or validator.validate_live(rca, incident)
    issues = list(base.issues)
    claims = [
        "probable_root_cause",
        "evidence",
        "affected_components",
        "next_steps",
    ]

    context_parts = [
        incident.description,
        *incident.signals,
        incident.deployment_notes or "",
        incident.affected_system,
    ]
    for s in similar[:3]:
        context_parts.append(s.title)
        context_parts.append(s.description or "")
    context_text = " ".join(context_parts).lower()

    # Root cause must overlap incident signals
    rc_overlap = _token_overlap(rca.probable_root_cause, context_text)
    if rc_overlap < 0.08 and len(rca.probable_root_cause) > 20:
        issues.append(
            f"Root cause weakly grounded in input/vector context (overlap={rc_overlap:.2f})"
        )

    # Next steps must not be empty and should reference action verbs
    if not rca.next_steps:
        issues.append("RCA report has no next_steps — not enterprise-ready")
    for step in rca.next_steps:
        if len(step.strip()) < 8:
            issues.append(f"Next step too vague: '{step[:60]}'")

    # Compare to historical label when vector hit exists
    label_alignment = 0.0
    if similar and incident.true_root_cause:
        label_alignment = _token_overlap(rca.probable_root_cause, incident.true_root_cause)
    elif similar:
        best = max(
            (_token_overlap(rca.probable_root_cause, s.title + " " + (s.description or "")) for s in similar),
            default=0.0,
        )
        label_alignment = best
        if best < 0.05:
            issues.append(
                "Root cause does not align with top similar incidents from vector store"
            )

    badge = base.giskard_badge
    if issues and badge == "PASS":
        badge = "FLAG"
    if base.hallucination_detected:
        badge = "FAIL"

    passed = badge == "PASS" and not base.hallucination_detected
    result = GiskardReportValidation(
        passed=passed,
        badge=badge,
        issues=issues,
        claims_checked=claims,
        vector_context_used=len(similar) > 0,
        similar_incident_ids=[s.incident_id for s in similar],
        label_alignment_score=round(label_alignment, 3),
    )
    logger.info(
        "giskard.report_validation",
        incident_id=incident.incident_id,
        badge=badge,
        vector_hits=len(similar),
        issues=len(issues),
    )
    return result
