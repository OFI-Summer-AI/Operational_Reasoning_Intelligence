"""
Trust & quality assessment layer — three modes:
1. validate_live(): trust checks on every RCA (Python rules — no LLM)
2. run_giskard_scan(): full giskard.scan() when you run main.py --mode giskard-scan
"""
from typing import Literal

import structlog
from pydantic import BaseModel

from layers.ingestion.schema import UnifiedIncident
from layers.reasoning.rca_output import RCAOutput

logger = structlog.get_logger(__name__)


class ValidationResult(BaseModel):
    """Result of validating a single RCAOutput against its source incident."""

    passed: bool
    confidence_score: int
    hallucination_detected: bool
    grounding_score: float
    issues: list[str]
    giskard_badge: Literal["PASS", "FLAG", "FAIL"]


class RCAValidator:
    """Validates RCA outputs for grounding and hallucination."""

    def validate_live(
        self,
        rca: RCAOutput,
        original_incident: UnifiedIncident,
    ) -> ValidationResult:
        """
        Custom real-time grounding check.
        Does NOT call Giskard — runs synchronously on every live RCA.
        """
        issues: list[str] = []
        all_signal_text = " ".join(
            [
                original_incident.description,
                *original_incident.signals,
                original_incident.deployment_notes or "",
                original_incident.affected_system,
            ]
        ).lower()

        # Check 1: Evidence items must reference words from input signals
        grounding_hits = 0
        for ev in rca.evidence:
            ev_words = set(ev.lower().split())
            signal_words = set(all_signal_text.split())
            overlap = ev_words & signal_words
            meaningful_overlap = {
                w for w in overlap if len(w) > 3
            }  # ignore stop words
            if len(meaningful_overlap) >= 2:
                grounding_hits += 1
            else:
                issues.append(f"Evidence not grounded in signals: '{ev[:80]}...'")

        grounding_score = (grounding_hits / len(rca.evidence)) if rca.evidence else 0.0

        # Check 2: Affected components must appear in signals/notes
        hallucination_detected = False
        for component in rca.affected_components:
            if component.lower() not in all_signal_text:
                issues.append(f"Component '{component}' not found in input signals")
                hallucination_detected = True

        # Check 3: Confidence sanity — P1 with confidence < 20 is suspicious
        if original_incident.severity == "P1" and rca.confidence < 20:
            issues.append(
                f"Suspiciously low confidence ({rca.confidence}) for P1 incident"
            )

        # Check 4: Empty evidence is a red flag
        if not rca.evidence:
            issues.append("No evidence provided — RCA is ungrounded")
            grounding_score = 0.0

        # Determine badge
        if hallucination_detected:
            badge: Literal["PASS", "FLAG", "FAIL"] = "FAIL"
        elif issues:
            badge = "FLAG"
        else:
            badge = "PASS"

        passed = badge == "PASS"
        result = ValidationResult(
            passed=passed,
            confidence_score=rca.confidence,
            hallucination_detected=hallucination_detected,
            grounding_score=round(grounding_score, 3),
            issues=issues,
            giskard_badge=badge,
        )
        logger.info(
            "trust.validation",
            badge=badge,
            hallucination=hallucination_detected,
            grounding=round(grounding_score, 3),
            issues_count=len(issues),
            incident_id=original_incident.incident_id,
        )
        return result

    def run_giskard_scan(self, model, dataset) -> object:
        """
        Full Giskard scan — call pre-deployment and weekly.
        model: giskard.Model, dataset: giskard.Dataset
        Returns giskard.ScanResult
        """
        try:
            import giskard

            logger.info("giskard.scan_start")
            # verbose=False avoids Windows console emoji encoding errors during scan
            scan_result = giskard.scan(model, dataset, verbose=False, raise_exceptions=False)
            logger.info("giskard.scan_complete")
            return scan_result
        except Exception as e:
            logger.error("giskard.scan_failed", error=str(e), exc_info=True)
            raise
