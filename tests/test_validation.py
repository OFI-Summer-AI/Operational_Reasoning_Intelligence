"""Tests for the validation layer."""
import pytest
from layers.validation.validator import RCAValidator, ValidationResult
from layers.reasoning.rca_output import RCAOutput


@pytest.fixture
def validator():
    return RCAValidator()


def test_validate_live_pass(validator, sample_incident, sample_rca):
    result = validator.validate_live(sample_rca, sample_incident)
    assert isinstance(result, ValidationResult)
    assert result.giskard_badge in ("PASS", "FLAG", "FAIL")


def test_validate_live_hallucination_detected(validator, sample_incident):
    """Component not in signals should be flagged as hallucination."""
    rca = RCAOutput(
        probable_root_cause="Test",
        confidence=80,
        affected_components=["nonexistent-service-xyz"],
        evidence=["connection pool exhausted"],
        next_steps=["fix it"],
    )
    result = validator.validate_live(rca, sample_incident)
    assert result.hallucination_detected is True
    assert result.giskard_badge == "FAIL"


def test_validate_live_grounding(validator, sample_incident, sample_rca):
    result = validator.validate_live(sample_rca, sample_incident)
    assert 0.0 <= result.grounding_score <= 1.0


def test_validate_live_empty_evidence(validator, sample_incident):
    rca = RCAOutput(
        probable_root_cause="Unknown",
        confidence=50,
        affected_components=[],
        evidence=[],
        next_steps=["investigate"],
    )
    result = validator.validate_live(rca, sample_incident)
    assert result.grounding_score == 0.0
    assert any("evidence" in issue.lower() for issue in result.issues)


def test_validate_live_low_confidence_p1(validator, sample_incident):
    rca = RCAOutput(
        probable_root_cause="Unknown",
        confidence=5,
        affected_components=[],
        evidence=["connection pool exhausted"],
        next_steps=["investigate"],
    )
    result = validator.validate_live(rca, sample_incident)
    assert any("confidence" in issue.lower() for issue in result.issues)


def test_validation_result_model():
    result = ValidationResult(
        passed=True,
        confidence_score=85,
        hallucination_detected=False,
        grounding_score=0.9,
        issues=[],
        giskard_badge="PASS",
    )
    assert result.passed is True
    assert result.giskard_badge == "PASS"
