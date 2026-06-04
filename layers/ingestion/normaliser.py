"""Normalise raw dicts from any parser into UnifiedIncident."""
from datetime import datetime
from typing import Any, Literal
import uuid

import structlog

from layers.ingestion.schema import UnifiedIncident
from layers.ingestion.text_utils import normalize_unicode_text

logger = structlog.get_logger(__name__)

_SEVERITY_MAP = {
    "critical": "P1",
    "high": "P2",
    "medium": "P3",
    "low": "P4",
    "p1": "P1",
    "p2": "P2",
    "p3": "P3",
    "p4": "P4",
    "1": "P1",
    "2": "P2",
    "3": "P3",
    "4": "P4",
}


def _coerce_severity(raw: Any) -> Literal["P1", "P2", "P3", "P4"]:
    return _SEVERITY_MAP.get(str(raw).strip().lower(), "P3")  # type: ignore[return-value]


def _coerce_signals(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(s) for s in raw if s]
    if isinstance(raw, str) and raw.strip():
        return [s.strip() for s in raw.split("\n") if s.strip()]
    return []


def _coerce_datetime(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return datetime.utcnow()


def normalise(raw: dict[str, Any], source_dataset: str = "unknown") -> UnifiedIncident | None:
    """Convert a raw parser dict to UnifiedIncident. Returns None on failure."""
    try:
        incident_id = str(raw.get("incident_id") or raw.get("id") or uuid.uuid4())
        title = str(
            raw.get("title") or raw.get("name") or raw.get("summary") or "Untitled Incident"
        )
        description = str(
            raw.get("description")
            or raw.get("desc")
            or raw.get("details")
            or raw.get("raw_text", "")
        )[:2000]

        signals_raw = raw.get("signals") or raw.get("alerts") or raw.get("logs") or []
        signals = _coerce_signals(signals_raw)
        if not signals and description:
            # Treat description lines as minimal signals
            signals = [description[:300]]

        return UnifiedIncident(
            incident_id=incident_id,
            title=normalize_unicode_text(title)[:200],
            description=normalize_unicode_text(description),
            severity=_coerce_severity(
                raw.get("severity") or raw.get("priority") or raw.get("impact") or "P3"
            ),
            affected_system=str(
                raw.get("affected_system")
                or raw.get("system")
                or raw.get("service")
                or raw.get("category")
                or "unknown"
            )[:100],
            signals=[normalize_unicode_text(s) for s in signals],
            deployment_notes=(
                normalize_unicode_text(str(raw["deployment_notes"]))
                if raw.get("deployment_notes")
                else None
            ),
            created_at=_coerce_datetime(
                raw.get("created_at") or raw.get("timestamp") or raw.get("date")
            ),
            source_dataset=str(raw.get("source_dataset") or source_dataset),
            true_root_cause=(
                normalize_unicode_text(str(raw["true_root_cause"]))
                if raw.get("true_root_cause")
                else None
            ),
            raw_text=str(raw.get("raw_text") or "")[:5000],
        )
    except Exception as e:
        logger.error("normaliser.failed", raw_keys=list(raw.keys()), error=str(e), exc_info=True)
        return None


def normalise_batch(
    records: list[dict[str, Any]], source_dataset: str = "unknown"
) -> list[UnifiedIncident]:
    """Normalise a list of raw dicts, logging every failure."""
    results: list[UnifiedIncident] = []
    failed = 0
    for record in records:
        incident = normalise(record, source_dataset)
        if incident:
            results.append(incident)
        else:
            failed += 1
    logger.info(
        "normaliser.batch_done",
        total=len(records),
        succeeded=len(results),
        failed=failed,
        source_dataset=source_dataset,
    )
    return results
