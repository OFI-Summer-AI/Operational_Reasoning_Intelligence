"""Live Giskard scan — single row, no Groq in predict."""
import asyncio
import sys
import types
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from config.settings import Settings
from layers.ingestion.schema import UnifiedIncident
from layers.reasoning.rca_output import RCAOutput
from layers.validation.live_giskard import (
    _build_live_dataset,
    _create_live_giskard_model,
    run_live_giskard_scan,
)
from layers.validation.report_validator import GiskardReportValidation
from layers.validation.validator import ValidationResult


@pytest.fixture
def sample_incident():
    return UnifiedIncident(
        incident_id="test-001",
        title="API timeout",
        description="Gateway errors spike",
        severity="P2",
        affected_system="api-gateway",
        signals=["ERROR timeout", "ALERT latency high"],
        deployment_notes="v2.1 deployed",
        source_dataset="test",
    )


@pytest.fixture
def sample_rca():
    return RCAOutput(
        probable_root_cause="Connection pool exhausted on api-gateway",
        confidence=72,
        evidence=["ERROR timeout", "ALERT latency high"],
        next_steps=["Scale pool", "Rollback v2.1"],
    )


@pytest.fixture
def fake_giskard(monkeypatch):
    class FakeModel:
        def __init__(self, model=None, **kwargs):
            self._predict = model

        def predict(self, df):
            return self._predict(df)

    mod = types.ModuleType("giskard")
    mod.Model = FakeModel
    mod.Dataset = lambda **kw: types.SimpleNamespace(df=kw["df"], name=kw.get("name", ""))
    monkeypatch.setitem(sys.modules, "giskard", mod)
    return mod


def test_create_live_model_returns_cached_rca(fake_giskard, sample_rca):
    model = _create_live_giskard_model(sample_rca)
    df = pd.DataFrame([{"incident_id": "x", "signals": "a"}])
    out = model.predict(df)
    assert out.iloc[0]["root_cause"] == sample_rca.probable_root_cause


def test_build_live_dataset_has_vector_context(fake_giskard, sample_incident):
    from layers.ingestion.schema import SimilarIncident

    similar = [
        SimilarIncident(
            incident_id="hist-1",
            title="Past pool issue",
            description="pool full",
            similarity_score=0.88,
        )
    ]
    ds = _build_live_dataset(sample_incident, similar)
    assert "hist-1" in ds.df.iloc[0]["vector_context"]


def test_run_live_giskard_disabled(monkeypatch, sample_incident, sample_rca):
    monkeypatch.setenv("GISKARD_LIVE_SCAN", "false")
    settings = Settings()
    validation = ValidationResult(
        passed=True,
        confidence_score=80,
        hallucination_detected=False,
        grounding_score=0.9,
        issues=[],
        giskard_badge="PASS",
    )
    report_val = GiskardReportValidation(
        passed=True,
        badge="PASS",
        issues=[],
        claims_checked=[],
        label_alignment_score=0.9,
        vector_context_used=False,
    )
    result = asyncio.run(
        run_live_giskard_scan(
            sample_incident, sample_rca, [], settings, validation, report_val
        )
    )
    assert result["enabled"] is False


def test_run_live_giskard_scan_writes_html(fake_giskard, tmp_path, sample_incident, sample_rca):
    settings = Settings(
        giskard_live_scan=True,
        giskard_scan_enabled=True,
        giskard_eval_report_dir=str(tmp_path),
    )
    validation = ValidationResult(
        passed=True,
        confidence_score=80,
        hallucination_detected=False,
        grounding_score=0.9,
        issues=[],
        giskard_badge="PASS",
    )
    report_val = GiskardReportValidation(
        passed=True,
        badge="PASS",
        issues=[],
        claims_checked=[],
        label_alignment_score=0.9,
        vector_context_used=False,
    )

    mock_scan = MagicMock()
    mock_scan.issues = []
    mock_scan.has_issues = lambda: False
    mock_scan.detectors_names = ["StubDetector"]
    mock_scan.to_json.return_value = '{"StubDetector": {}}'
    mock_scan.to_html = MagicMock()

    with patch(
        "layers.validation.live_giskard.RCAValidator.run_giskard_scan",
        return_value=mock_scan,
    ):
        with patch(
            "layers.validation.live_giskard.run_governance_checks",
            return_value={"passed": True, "failures": []},
        ):
            result = asyncio.run(
                run_live_giskard_scan(
                    sample_incident, sample_rca, [], settings, validation, report_val
                )
            )

    assert result["enabled"] is True
    assert result["giskard_scan"] is not None
    assert result["giskard_native_html"]
    mock_scan.to_html.assert_called_once()
