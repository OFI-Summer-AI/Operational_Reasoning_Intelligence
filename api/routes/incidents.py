import time
from typing import Annotated

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from config.settings import Settings, get_settings
from layers.pipeline.enterprise import run_enterprise_rca
from layers.output.report import RCAReport

router = APIRouter()
logger = structlog.get_logger(__name__)

# Simple in-memory history store (replace with DB for production)
_history: list[RCAReport] = []


class IncidentInput(BaseModel):
    incident_id: str | None = None
    title: str
    description: str
    severity: str = "P3"
    affected_system: str = "unknown"
    signals: list[str] = []
    deployment_notes: str | None = None
    source_dataset: str = "api"
    true_root_cause: str | None = None


@router.post("/api/incidents/analyze", response_model=RCAReport)
async def analyze_incident(
    incident_input: IncidentInput,
    background_tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RCAReport:
    """Enterprise pipeline: ingestion QA → ChromaDB → Groq → trust validation."""
    try:
        result = await run_enterprise_rca(
            incident_input.model_dump(),
            settings,
            source_dataset="api",
        )
    except Exception as e:
        logger.error("api.rca_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"RCA pipeline failed: {e}")

    if result.get("error"):
        raise HTTPException(
            status_code=422,
            detail={
                "message": result["error"],
                "ingestion_errors": result.get("ingestion_errors", []),
            },
        )

    report = RCAReport.model_validate(
        {k: v for k, v in result.items() if k in RCAReport.model_fields}
    )

    background_tasks.add_task(_store_in_history, report)
    trace = result.get("pipeline_trace") or {}
    logger.info(
        "api.analyze_complete",
        incident_id=report.incident_id,
        badge=report.giskard_badge,
        latency_ms=trace.get("total_ms", report.total_latency_ms),
        giskard_mode=settings.effective_giskard_mode,
    )
    return report


@router.get("/api/incidents/history", response_model=list[RCAReport])
async def get_history(limit: int = 20) -> list[RCAReport]:
    """Return the most recent RCA reports."""
    return _history[-limit:]


def _store_in_history(report: RCAReport) -> None:
    _history.append(report)
    if len(_history) > 500:
        _history.pop(0)
