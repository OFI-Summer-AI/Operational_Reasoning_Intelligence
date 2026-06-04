"""Per-incident Giskard scan after Groq RCA — one row, no extra Groq in predict()."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from config.settings import Settings
from layers.ingestion.schema import SimilarIncident, UnifiedIncident
from layers.reasoning.rca_output import RCAOutput
from layers.validation.giskard_ui import extract_scan_payload
from layers.validation.report_validator import GiskardReportValidation
from layers.validation.test_suite import run_governance_checks
from layers.validation.validator import RCAValidator, ValidationResult

logger = structlog.get_logger(__name__)


def _build_live_dataset(incident: UnifiedIncident, similar: list[SimilarIncident]) -> object:
    import giskard

    vector_context = ""
    if similar:
        parts = [
            f"[{s.incident_id}] {s.title} (score={s.similarity_score:.2f})"
            for s in similar[:3]
        ]
        vector_context = " | ".join(parts)

    df = pd.DataFrame(
        [
            {
                "incident_id": incident.incident_id,
                "title": incident.title,
                "description": incident.description,
                "severity": incident.severity,
                "affected_system": incident.affected_system,
                "signals": "\n".join(incident.signals),
                "deployment_notes": incident.deployment_notes or "",
                "vector_context": vector_context,
                "true_root_cause": incident.true_root_cause or "",
            }
        ]
    )
    return giskard.Dataset(
        df=df,
        target="true_root_cause",
        name=f"ORI Live — {incident.incident_id}",
    )


def _create_live_giskard_model(rca: RCAOutput) -> object:
    """Giskard model returns the RCA we already generated — predict() does not call Groq."""
    import giskard

    def predict(df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "root_cause": rca.probable_root_cause,
                    "confidence": rca.confidence,
                    "evidence_summary": "; ".join(rca.evidence[:5]),
                }
            ]
        )

    return giskard.Model(
        model=predict,
        model_type="text_generation",
        name="ORI Live RCA (single incident)",
        description="Uses Groq RCA output; Giskard scan validates that output only",
        feature_names=[
            "incident_id",
            "signals",
            "deployment_notes",
            "affected_system",
            "description",
            "title",
            "severity",
            "vector_context",
        ],
    )


async def run_live_giskard_scan(
    incident: UnifiedIncident,
    rca: RCAOutput,
    similar: list[SimilarIncident],
    settings: Settings,
    validation: ValidationResult,
    report_val: GiskardReportValidation,
) -> dict[str, Any]:
    """
    Run giskard.scan() on one incident row after RCA is produced.
    No additional Groq calls inside Giskard predict().
    """
    report_dir = Path(settings.giskard_eval_report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    safe_id = incident.incident_id.replace("/", "-")
    html_path = report_dir / f"live_{safe_id}_giskard.html"
    json_path = report_dir / f"live_{safe_id}_giskard.json"

    result: dict[str, Any] = {
        "enabled": True,
        "giskard_native_html": None,
        "giskard_scan": None,
        "giskard_suite": None,
        "what_giskard_did": [],
        "extra_groq_calls": 0,
    }

    if not settings.giskard_scan_enabled or not settings.giskard_live_scan:
        result["enabled"] = False
        result["what_giskard_did"].append("Giskard live scan disabled in settings.")
        return result

    model = _create_live_giskard_model(rca)
    dataset = _build_live_dataset(incident, similar)
    validator = RCAValidator()

    result["what_giskard_did"].append(
        "Built a single-row Giskard dataset from your pasted signals and optional ChromaDB context."
    )
    result["what_giskard_did"].append(
        "Wrapped the Groq RCA output as the model prediction (predict does not call Groq again)."
    )

    try:
        logger.info("live_giskard.scan_start", incident_id=incident.incident_id)
        scan_result = validator.run_giskard_scan(model, dataset)
        payload = extract_scan_payload(scan_result)
        result["giskard_scan"] = payload
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        scan_result.to_html(str(html_path))
        result["giskard_native_html"] = str(html_path)
        result["what_giskard_did"].append(
            f"Ran giskard.scan on this incident → {html_path.name} "
            f"({payload.get('issue_count', 0)} detector issue(s))."
        )
        logger.info(
            "live_giskard.scan_saved",
            path=str(html_path),
            issues=payload.get("issue_count"),
        )
    except Exception as e:
        logger.warning("live_giskard.scan_failed", error=str(e))
        result["giskard_scan"] = {
            "has_issues": True,
            "issue_count": 0,
            "issues": [],
            "scan_logs": [
                {
                    "detector": "giskard.scan",
                    "level": "error",
                    "message": str(e),
                    "help": "Install giskard dependencies or check logs/giskard.log",
                }
            ],
        }
        result["what_giskard_did"].append(f"Giskard scan failed: {e}")

    try:
        suite = run_governance_checks(model, dataset)
        result["giskard_suite"] = suite
        if not suite.get("passed"):
            result["what_giskard_did"].append(
                f"Governance checks flagged {len(suite.get('failures', []))} issue(s) on cached RCA shape."
            )
        else:
            result["what_giskard_did"].append("Governance checks on RCA output shape: passed.")
    except Exception as e:
        logger.warning("live_giskard.suite_failed", error=str(e))

    return result
