from layers.validation.trust_kpis import build_governance_business_kpis, compute_trust_kpis


def test_compute_trust_kpis_measures_draft_time_and_grounding():
    out = {
        "total_latency_ms": 45_000,
        "hallucination_detected": False,
        "giskard_badge": "PASS",
        "grounding_audit": {
            "evidence_citations": [
                {"grounded": "yes"},
                {"grounded": "yes"},
                {"grounded": "no"},
            ],
        },
        "giskard_report_validation": {},
    }
    kpis = compute_trust_kpis(out)
    assert "disclaimer" in kpis
    assert len(kpis["kpis"]) == 5
    draft = next(r for r in kpis["kpis"] if r["kpi"] == "RCA draft time")
    assert draft["met"] is True
    assert draft["observed_value"] == 45.0
    grounded = next(r for r in kpis["kpis"] if r["kpi"] == "Grounded evidence rate")
    assert abs(grounded["observed_value"] - 2 / 3) < 0.01


def test_governance_business_kpis_from_summary():
    summary = {
        "eval_sample_size": 5,
        "mean_reasoning_ms": 150_000,
        "hallucination_rate": 0.0,
        "mean_grounding_score": 0.95,
        "mean_label_alignment": 0.4,
    }
    rows = build_governance_business_kpis(summary)
    assert len(rows) >= 5
    draft = next(r for r in rows if r["kpi"] == "RCA draft time")
    assert draft["met"] is False
