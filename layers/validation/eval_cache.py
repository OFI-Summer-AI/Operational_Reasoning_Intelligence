"""Disk cache for governance RCA predictions (avoids repeat LLM calls)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field

from config.settings import Settings
from layers.ingestion.schema import SimilarIncident, UnifiedIncident
from layers.reasoning.rca_output import RCAOutput
from layers.validation.validator import ValidationResult

logger = structlog.get_logger(__name__)


def compute_prompt_hash(settings: Settings) -> str:
    """Invalidate cache when prompts or model change."""
    prompts_path = Path(__file__).resolve().parent.parent / "reasoning" / "prompts.py"
    blob = prompts_path.read_bytes() + settings.groq_model.encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


class CachedPrediction(BaseModel):
    incident_id: str
    probable_root_cause: str
    confidence: int
    evidence_summary: str
    grounding_score: float
    trust_badge: str
    hallucination_detected: bool
    label_alignment_score: float
    similar_incident_ids: list[str] = Field(default_factory=list)
    reasoning_ms: int = 0
    cached_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EvalCache:
    """JSON file cache keyed by incident_id under a prompt_hash namespace."""

    def __init__(self, path: str, prompt_hash: str) -> None:
        self.path = Path(path)
        self.prompt_hash = prompt_hash
        self._data: dict[str, Any] = {"prompt_hash": prompt_hash, "predictions": {}}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("eval_cache.load_failed", path=str(self.path), error=str(e))
            return
        if raw.get("prompt_hash") == self.prompt_hash:
            self._data = raw
        else:
            logger.info(
                "eval_cache.hash_mismatch",
                stored=raw.get("prompt_hash"),
                current=self.prompt_hash,
            )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, indent=2, default=str),
            encoding="utf-8",
        )

    def get(self, incident_id: str) -> CachedPrediction | None:
        row = self._data.get("predictions", {}).get(incident_id)
        if not row:
            return None
        return CachedPrediction(**row)

    def put(
        self,
        incident: UnifiedIncident,
        rca: RCAOutput,
        validation: ValidationResult,
        similar: list[SimilarIncident],
        reasoning_ms: int,
    ) -> CachedPrediction:
        alignment = label_alignment_score(rca.probable_root_cause, incident.true_root_cause or "")
        entry = CachedPrediction(
            incident_id=incident.incident_id,
            probable_root_cause=rca.probable_root_cause,
            confidence=rca.confidence,
            evidence_summary="; ".join(rca.evidence[:2]),
            grounding_score=validation.grounding_score,
            trust_badge=validation.giskard_badge,
            hallucination_detected=validation.hallucination_detected,
            label_alignment_score=round(alignment, 3),
            similar_incident_ids=[s.incident_id for s in similar],
            reasoning_ms=reasoning_ms,
        )
        self._data.setdefault("predictions", {})[incident.incident_id] = entry.model_dump()
        return entry

    def entries_for(self, incident_ids: list[str]) -> list[CachedPrediction]:
        out: list[CachedPrediction] = []
        for iid in incident_ids:
            row = self.get(iid)
            if row:
                out.append(row)
        return out


def build_governance_summary(
    sampled: list[UnifiedIncident],
    cache: EvalCache,
    *,
    pool_size: int,
    new_llm_runs: int,
    suite_passed: bool | None,
) -> dict[str, Any]:
    entries = cache.entries_for([i.incident_id for i in sampled])
    n = len(entries) or 1
    trust_pass = sum(1 for e in entries if e.trust_badge == "PASS")
    hallucination = sum(1 for e in entries if e.hallucination_detected)
    mean_ms = round(sum(e.reasoning_ms for e in entries) / n, 1)
    summary = {
        "eval_sample_size": len(sampled),
        "eval_pool_size": pool_size,
        "new_llm_rca_runs": new_llm_runs,
        "estimated_groq_calls": new_llm_runs,
        "trust_pass_rate": round(trust_pass / n, 3),
        "hallucination_rate": round(hallucination / n, 3),
        "mean_grounding_score": round(sum(e.grounding_score for e in entries) / n, 3),
        "mean_label_alignment": round(sum(e.label_alignment_score for e in entries) / n, 3),
        "mean_reasoning_ms": mean_ms,
        "giskard_suite_passed": suite_passed,
        "incidents": [e.model_dump() for e in entries],
    }
    from layers.validation.trust_kpis import build_governance_business_kpis

    summary["business_kpis"] = build_governance_business_kpis(summary)
    return summary


def label_alignment_score(probable: str, true_root_cause: str) -> float:
    """Keyword overlap between model output and labelled root cause (no LLM)."""
    if not true_root_cause or not probable:
        return 0.0
    p_words = {w for w in probable.lower().split() if len(w) > 4}
    t_words = {w for w in true_root_cause.lower().split() if len(w) > 4}
    if not t_words:
        return 0.0
    overlap = p_words & t_words
    if not overlap:
        return 0.0
    return min(1.0, len(overlap) / max(3, len(t_words)))
