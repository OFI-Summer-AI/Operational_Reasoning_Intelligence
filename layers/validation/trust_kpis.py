"""Business KPIs for trust & quality assessment (risk, not correctness)."""
from __future__ import annotations

from typing import Any

TRUST_DISCLAIMER = (
    "PASS / FLAG / FAIL measure **risk** (grounding, hallucination, detector issues) — "
    "not whether the root cause is **correct**. "
    "Example: “Database saturation” can pass while the true cause is “connection pool exhaustion”."
)

# Executive targets (POC / pilot). Operational KPIs need production tracking.
KPI_TARGETS: dict[str, dict[str, Any]] = {
    "rca_draft_time": {
        "label": "RCA draft time",
        "target_display": "< 2 min",
        "target_value": 120.0,
        "unit": "sec",
        "compare": "lte",
    },
    "hallucination_rate": {
        "label": "Hallucination rate",
        "target_display": "< 5%",
        "target_value": 0.05,
        "unit": "ratio",
        "compare": "lte",
    },
    "grounded_evidence_rate": {
        "label": "Grounded evidence rate",
        "target_display": "> 90%",
        "target_value": 0.90,
        "unit": "ratio",
        "compare": "gte",
    },
    "manual_investigation_reduction": {
        "label": "Manual investigation reduction",
        "target_display": "40%",
        "target_value": 0.40,
        "unit": "ratio",
        "compare": "gte",
        "tracked_in_production": True,
    },
    "rca_acceptance_rate": {
        "label": "RCA acceptance rate",
        "target_display": "> 80%",
        "target_value": 0.80,
        "unit": "ratio",
        "compare": "gte",
        "tracked_in_production": True,
    },
}


def _met(observed: float | None, spec: dict[str, Any]) -> bool | None:
    if observed is None:
        return None
    t = spec["target_value"]
    if spec["compare"] == "lte":
        return observed <= t
    return observed >= t


def _grounded_evidence_rate(audit: dict[str, Any]) -> float | None:
    rows = audit.get("evidence_citations") or []
    if not rows:
        return None
    ok = sum(1 for r in rows if r.get("grounded") in ("yes", "partial (historical)"))
    return round(ok / len(rows), 3)


def compute_trust_kpis(out: dict[str, Any]) -> dict[str, Any]:
    """Per-incident KPIs for UI/API (measurable on this run)."""
    trace = out.get("pipeline_trace") or {}
    total_ms = out.get("total_latency_ms") or trace.get("total_ms") or 0
    draft_sec = round(total_ms / 1000.0, 1) if total_ms else None

    audit = out.get("grounding_audit") or {}
    grounded_rate = _grounded_evidence_rate(audit)
    hallucination = bool(out.get("hallucination_detected"))
    hall_rate = 1.0 if hallucination else 0.0

    rv = out.get("giskard_report_validation") or {}
    label_align = rv.get("label_alignment_score")
    has_label = label_align is not None and label_align > 0

    rows: list[dict[str, Any]] = []

    spec = KPI_TARGETS["rca_draft_time"]
    rows.append(
        {
            "kpi": spec["label"],
            "target": spec["target_display"],
            "observed": f"{draft_sec}s" if draft_sec is not None else "—",
            "observed_value": draft_sec,
            "met": _met(draft_sec, spec) if draft_sec is not None else None,
            "scope": "this_run",
        }
    )

    spec = KPI_TARGETS["hallucination_rate"]
    rows.append(
        {
            "kpi": spec["label"],
            "target": spec["target_display"],
            "observed": f"{hall_rate * 100:.0f}% (this incident)",
            "observed_value": hall_rate,
            "met": _met(hall_rate, spec),
            "scope": "this_run",
        }
    )

    spec = KPI_TARGETS["grounded_evidence_rate"]
    rows.append(
        {
            "kpi": spec["label"],
            "target": spec["target_display"],
            "observed": f"{grounded_rate * 100:.0f}%" if grounded_rate is not None else "—",
            "observed_value": grounded_rate,
            "met": _met(grounded_rate, spec) if grounded_rate is not None else None,
            "scope": "this_run",
        }
    )

    for key in ("manual_investigation_reduction", "rca_acceptance_rate"):
        spec = KPI_TARGETS[key]
        rows.append(
            {
                "kpi": spec["label"],
                "target": spec["target_display"],
                "observed": "Track in production (ops survey / MTTR)",
                "observed_value": None,
                "met": None,
                "scope": "production",
            }
        )

    return {
        "disclaimer": TRUST_DISCLAIMER,
        "trust_badge": out.get("giskard_badge"),
        "risk_tier": out.get("giskard_badge"),
        "label_alignment_score": label_align if has_label else None,
        "label_alignment_note": (
            "Compared to labelled root cause in dataset (correctness proxy)."
            if has_label
            else "No labelled root cause on this incident."
        ),
        "kpis": rows,
    }


def build_governance_business_kpis(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Batch eval KPIs vs targets for governance_report.html."""
    mean_ms = summary.get("mean_reasoning_ms") or 0
    draft_sec = mean_ms / 1000.0
    hall = summary.get("hallucination_rate", 0)
    grounding = summary.get("mean_grounding_score", 0)
    align = summary.get("mean_label_alignment", 0)
    n = summary.get("eval_sample_size", 0)

    rows: list[dict[str, Any]] = []

    spec = KPI_TARGETS["rca_draft_time"]
    rows.append(
        {
            "kpi": spec["label"],
            "target": spec["target_display"],
            "observed": f"{draft_sec:.1f}s avg (reasoning, n={n})",
            "met": _met(draft_sec, spec),
        }
    )
    spec = KPI_TARGETS["hallucination_rate"]
    rows.append(
        {
            "kpi": spec["label"],
            "target": spec["target_display"],
            "observed": f"{hall * 100:.1f}% on sample",
            "met": _met(hall, spec),
        }
    )
    spec = KPI_TARGETS["grounded_evidence_rate"]
    rows.append(
        {
            "kpi": spec["label"],
            "target": spec["target_display"],
            "observed": f"{grounding * 100:.1f}% mean grounding score (proxy)",
            "met": _met(grounding, spec),
        }
    )
    rows.append(
        {
            "kpi": "Label alignment (correctness proxy)",
            "target": "Informative only",
            "observed": f"{align * 100:.1f}% mean overlap vs true_root_cause",
            "met": None,
        }
    )
    for key in ("manual_investigation_reduction", "rca_acceptance_rate"):
        spec = KPI_TARGETS[key]
        rows.append(
            {
                "kpi": spec["label"],
                "target": spec["target_display"],
                "observed": "Requires pilot metrics",
                "met": None,
            }
        )
    return rows
