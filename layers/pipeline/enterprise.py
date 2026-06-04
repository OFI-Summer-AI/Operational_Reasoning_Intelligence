"""Enterprise pipeline: ingestion QA → memory → LLM → trust validation → report."""
from __future__ import annotations

import time
from typing import Any

import structlog

from config.settings import Settings
from layers.ingestion.input_validation import validate_user_input
from layers.memory.vector_store import IncidentVectorStore
from layers.output.formatter import to_dict
from layers.output.report import assemble_report
from layers.pipeline.context_enrichment import enrich_next_steps_from_vector
from layers.reasoning.chain import RCAChain
from layers.validation.giskard_ui import (
    build_grounding_audit,
    build_outcome_explanation,
    collect_findings,
    compute_outcome,
)
from layers.validation.live_giskard import run_live_giskard_scan
from layers.validation.trust_kpis import compute_trust_kpis
from layers.validation.report_validator import validate_rca_report
from layers.validation.validator import RCAValidator, ValidationResult

logger = structlog.get_logger(__name__)


async def run_enterprise_rca(
    raw: dict[str, Any],
    settings: Settings,
    *,
    source_dataset: str = "user_input",
) -> dict[str, Any]:
    """
    Production path for UI/API/CLI single incidents.

    - Ingestion QA gate (no Groq if invalid)
    - ChromaDB top-k similar incidents
    - Groq single-call RCA
    - Trust layer: ORI rules + one-row giskard.scan (no extra Groq in Giskard predict)
    """
    trace: dict[str, Any] = {"scan_mode": "live_giskard"}
    t_total = time.monotonic()

    incident, ing_errors, ing_warnings = validate_user_input(raw, source_dataset=source_dataset)
    trace["input_validation"] = {
        "passed": incident is not None,
        "errors": ing_errors,
        "warnings": ing_warnings,
    }
    if incident is None:
        logger.info("pipeline.ingestion_failed", errors=ing_errors)
        return {
            "error": "; ".join(ing_errors) or "Ingestion validation failed",
            "ingestion_errors": ing_errors,
            "ingestion_warnings": ing_warnings,
            "pipeline_trace": trace,
            "outcome": "issues_detected",
        }

    logger.info(
        "pipeline.ingestion_ok",
        incident_id=incident.incident_id,
        title=incident.title[:60],
        signal_count=len(incident.signals),
    )

    t0 = time.monotonic()
    store = IncidentVectorStore(
        persist_dir=settings.chromadb_persist_dir,
        collection_name=settings.chromadb_collection_name,
        embedding_model=settings.embedding_model,
        embedding_cache_dir=settings.embedding_cache_dir,
    )
    store_count = store.count()
    query = f"{incident.title} {incident.description} {' '.join(incident.signals[:3])}"
    similar = store.similarity_search(query, k=3)
    trace["memory_ms"] = int((time.monotonic() - t0) * 1000)
    trace["similar_count"] = len(similar)
    trace["chromadb_count"] = store_count
    logger.info(
        "pipeline.memory",
        incident_id=incident.incident_id,
        similar_count=len(similar),
        chromadb_total=store_count,
        latency_ms=trace["memory_ms"],
    )

    t0 = time.monotonic()
    chain = RCAChain(settings)
    logger.info("pipeline.reasoning_start", incident_id=incident.incident_id, model=settings.groq_model)
    rca = await chain.run(incident, similar)
    trace["reasoning_ms"] = int((time.monotonic() - t0) * 1000)
    logger.info(
        "pipeline.reasoning_complete",
        incident_id=incident.incident_id,
        confidence=rca.confidence,
        latency_ms=trace["reasoning_ms"],
    )

    rca = rca.model_copy(
        update={
            "next_steps": enrich_next_steps_from_vector(rca, similar, store_count=store_count)
        }
    )

    validator = RCAValidator()
    validation = validator.validate_live(rca, incident)
    t0 = time.monotonic()
    report_val = validate_rca_report(rca, incident, similar, validation)
    trace["validation_ms"] = int((time.monotonic() - t0) * 1000)

    if report_val.badge in ("PASS", "FLAG", "FAIL"):
        validation = ValidationResult(
            passed=report_val.passed,
            confidence_score=validation.confidence_score,
            hallucination_detected=validation.hallucination_detected,
            grounding_score=validation.grounding_score,
            issues=list(dict.fromkeys(validation.issues + report_val.issues)),
            giskard_badge=report_val.badge,
        )

    t0 = time.monotonic()
    giskard_live = await run_live_giskard_scan(
        incident, rca, similar, settings, validation, report_val
    )
    trace["giskard_live_ms"] = int((time.monotonic() - t0) * 1000)
    trace["giskard_semi"] = giskard_live

    findings = collect_findings(
        giskard_scan=giskard_live.get("giskard_scan"),
        giskard_suite=giskard_live.get("giskard_suite"),
        report_validation=report_val.model_dump(),
        validation_issues=validation.issues,
    )
    grounding_audit = build_grounding_audit(
        incident, rca, similar, report_val.model_dump()
    )
    trace["total_ms"] = int((time.monotonic() - t_total) * 1000)

    report = assemble_report(
        incident_id=incident.incident_id,
        rca=rca,
        validation=validation,
        similar_incidents=similar,
        pipeline_trace=trace,
    )
    out = to_dict(report)
    out["ingestion_warnings"] = ing_warnings
    out["giskard_report_validation"] = report_val.model_dump()
    out["giskard_scan"] = giskard_live.get("giskard_scan")
    out["giskard_suite"] = giskard_live.get("giskard_suite")
    out["giskard_native_html"] = giskard_live.get("giskard_native_html")
    out["giskard_live_scan"] = giskard_live
    out["grounding_audit"] = grounding_audit
    out["what_giskard_did"] = giskard_live.get("what_giskard_did", [])
    out["giskard_findings"] = findings
    out["outcome"] = compute_outcome(findings, out.get("giskard_badge"))
    out["outcome_explanation"] = build_outcome_explanation(out, findings)
    out["trust_kpis"] = compute_trust_kpis(out)

    logger.info(
        "pipeline.complete",
        incident_id=out.get("incident_id"),
        outcome=out.get("outcome"),
        badge=out.get("giskard_badge"),
        findings=len(findings),
        total_ms=trace.get("total_ms"),
    )
    return out
