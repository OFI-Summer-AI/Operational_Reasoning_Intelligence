"""Input validation suite (testcases/input_validation.json)."""
from pathlib import Path

from layers.ingestion.input_validation import (
    load_validation_cases,
    run_all_input_validation_tests,
    validate_user_input,
)


def test_validate_user_input_pass():
    raw = {
        "title": "API timeout",
        "description": "Latency spike",
        "severity": "P2",
        "affected_system": "api",
        "signals": ["ERROR gateway: timeout"],
    }
    incident, errors, _ = validate_user_input(raw)
    assert incident is not None
    assert not errors


def test_validate_user_input_fail_no_signals():
    raw = {"title": "Empty", "description": "", "severity": "P1", "signals": []}
    incident, errors, _ = validate_user_input(raw)
    assert incident is None
    assert errors


def test_all_validation_cases_pass():
    summary = run_all_input_validation_tests()
    assert summary.failed == 0, [r for r in summary.results if not r.passed]


def test_cases_file_exists():
    assert Path("testcases/input_validation.json").exists()
    cases = load_validation_cases()
    assert len(cases) >= 5
