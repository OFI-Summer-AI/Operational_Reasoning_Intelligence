"""Governance dataset builder and trust checks (Giskard Dataset + local suite)."""
from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

_FORBIDDEN_OUTPUT = (
    "error:",
    "normalisation_failed",
    "parse error",
    "cache_miss",
    "not_in_eval_sample",
    "use_governance_warm_cache",
)


def build_giskard_dataset(synthetic_incidents) -> object:
    """Convert synthetic incidents to a giskard.Dataset."""
    import pandas as pd
    import giskard

    rows = []
    for inc in synthetic_incidents:
        rows.append(
            {
                "incident_id": inc.incident_id,
                "title": inc.title,
                "description": inc.description,
                "severity": inc.severity,
                "affected_system": inc.affected_system,
                "signals": "\n".join(inc.signals),
                "deployment_notes": inc.deployment_notes or "",
                "true_root_cause": inc.true_root_cause or "",
            }
        )
    df = pd.DataFrame(rows)
    return giskard.Dataset(
        df=df,
        target="true_root_cause",
        name="ORI Governance Eval Dataset",
    )


def _predictions_to_dataframe(preds) -> "pd.DataFrame":
    """Normalize Giskard ModelPredictionResults to a DataFrame."""
    import pandas as pd

    if hasattr(preds, "columns"):
        return preds
    raw = getattr(preds, "raw", None)
    if raw is None:
        raw = getattr(preds, "prediction", None)
    if raw is None:
        return pd.DataFrame()
    df = pd.DataFrame(raw)
    if df.shape[1] >= 3:
        df.columns = ["root_cause", "confidence", "evidence_summary"] + list(df.columns[3:])
    return df


def run_governance_checks(giskard_model, giskard_dataset) -> dict:
    """
    Lightweight governance suite (no extra LLM calls).
    Validates cache-backed model predictions on the eval sample.
    """
    raw_preds = giskard_model.predict(giskard_dataset)
    preds = _predictions_to_dataframe(raw_preds)
    failures: list[str] = []

    if preds.empty or "root_cause" not in preds.columns:
        failures.append("predict output missing root_cause column")
    else:
        for idx, row in preds.iterrows():
            rc = str(row.get("root_cause", ""))
            conf = int(row.get("confidence", 0) or 0)
            iid = giskard_dataset.df.iloc[idx]["incident_id"]
            if not rc or len(rc) < 10:
                failures.append(f"{iid}: root_cause too short or empty")
            if any(f in rc.lower() for f in _FORBIDDEN_OUTPUT):
                failures.append(f"{iid}: forbidden placeholder in root_cause")
            if conf < 1:
                failures.append(f"{iid}: confidence not set")

    passed = len(failures) == 0
    logger.info("governance.checks_complete", passed=passed, failure_count=len(failures))
    records = preds.to_dict(orient="records") if not preds.empty else []
    return {"passed": passed, "failures": failures, "predictions": records}
