from layers.validation.giskard_ui import (
    build_outcome_explanation,
    collect_findings,
    compute_outcome,
)


def test_compute_outcome_pass():
    assert compute_outcome([], "PASS") == "pass"


def test_compute_outcome_from_badge():
    assert compute_outcome([], "FAIL") == "issues_detected"


def test_collect_findings_merges_sources():
    findings = collect_findings(
        validation_issues=["Component not in signals"],
        giskard_suite={"failures": ["root_cause too short"]},
    )
    assert len(findings) >= 2
    assert compute_outcome(findings) == "issues_detected"


def test_build_outcome_explanation_pass():
    expl = build_outcome_explanation(
        {"giskard_badge": "PASS", "outcome": "pass", "giskard_report_validation": {}},
        [],
    )
    assert expl["outcome"] == "pass"
    assert "Low risk" in expl["headline"]


def test_build_outcome_explanation_issues():
    findings = [{"source": "trust", "level": "warning", "title": "x", "detail": "bad evidence"}]
    expl = build_outcome_explanation(
        {"giskard_badge": "FLAG", "outcome": "issues_detected"},
        findings,
    )
    assert expl["outcome"] == "issues_detected"
    assert len(expl["reasons"]) >= 1
