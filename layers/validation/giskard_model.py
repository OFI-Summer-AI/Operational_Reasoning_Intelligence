"""Wrap cached RCA predictions as a Giskard model for batch evaluation."""
from __future__ import annotations

import pandas as pd
import structlog

from layers.validation.eval_cache import EvalCache

logger = structlog.get_logger(__name__)


def create_cache_backed_giskard_model(
    cache: EvalCache,
    sampled_incidents: list,
) -> object:
    """
    Giskard model that reads pre-computed RCA from EvalCache (no LLM in predict).
    warm_eval_predictions() must run before checks / scan.
    """
    import giskard

    id_set = {i.incident_id for i in sampled_incidents}

    def predict(df: pd.DataFrame) -> pd.DataFrame:
        results = []
        for _, row in df.iterrows():
            iid = str(row.get("incident_id", ""))
            if iid not in id_set:
                results.append(
                    {
                        "root_cause": "not_in_eval_sample",
                        "confidence": 0,
                        "evidence_summary": "",
                    }
                )
                continue
            cached = cache.get(iid)
            if cached is None:
                results.append(
                    {
                        "root_cause": "cache_miss",
                        "confidence": 0,
                        "evidence_summary": "",
                    }
                )
                continue
            results.append(
                {
                    "root_cause": cached.probable_root_cause,
                    "confidence": cached.confidence,
                    "evidence_summary": cached.evidence_summary,
                }
            )
        return pd.DataFrame(results)

    return giskard.Model(
        model=predict,
        model_type="text_generation",
        name="ORI RCA Model (cache-backed)",
        description="Governance eval — predictions warmed via warm_eval_predictions()",
        feature_names=[
            "incident_id",
            "signals",
            "deployment_notes",
            "affected_system",
            "description",
            "title",
            "severity",
        ],
    )
