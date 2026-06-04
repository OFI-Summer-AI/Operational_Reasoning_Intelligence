"""Assemble the final RCAReport from all layer outputs."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from layers.ingestion.schema import SimilarIncident
from layers.reasoning.rca_output import RCAOutput
from layers.validation.validator import ValidationResult


class RCAReport(BaseModel):
    """Final report surfaced to consumers (API, UI, notebook)."""

    # Identity
    incident_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Core RCA
    probable_root_cause: str
    confidence: int
    affected_components: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)

    # Context
    similar_incidents: list[SimilarIncident] = Field(default_factory=list)

    # Trust layer
    giskard_badge: Literal["PASS", "FLAG", "FAIL"]
    validation_issues: list[str] = Field(default_factory=list)
    hallucination_detected: bool = False
    grounding_score: float = 0.0

    # Meta
    model_used: str = ""
    total_latency_ms: int = 0
    pipeline_trace: dict = Field(default_factory=dict)

    @computed_field
    @property
    def confidence_label(self) -> Literal["HIGH", "MEDIUM", "LOW"]:
        if self.confidence >= 70:
            return "HIGH"
        if self.confidence >= 40:
            return "MEDIUM"
        return "LOW"


def assemble_report(
    incident_id: str,
    rca: RCAOutput,
    validation: ValidationResult,
    similar_incidents: list[SimilarIncident],
    pipeline_trace: dict | None = None,
) -> RCAReport:
    """Build an RCAReport from layer outputs."""
    return RCAReport(
        incident_id=incident_id,
        probable_root_cause=rca.probable_root_cause,
        confidence=rca.confidence,
        affected_components=rca.affected_components,
        evidence=rca.evidence,
        next_steps=rca.next_steps,
        similar_incidents=similar_incidents,
        giskard_badge=validation.giskard_badge,
        validation_issues=validation.issues,
        hallucination_detected=validation.hallucination_detected,
        grounding_score=validation.grounding_score,
        model_used=rca.model_used,
        total_latency_ms=rca.latency_ms,
        pipeline_trace=pipeline_trace or {},
    )
