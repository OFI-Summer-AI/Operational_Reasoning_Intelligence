"""Tests for governance sampling, cache, and KPI summary (no Giskard/LLM)."""
import json
from pathlib import Path

import pytest

from config.settings import Settings
from layers.ingestion.schema import UnifiedIncident
from layers.validation.eval_cache import EvalCache, compute_prompt_hash, label_alignment_score
from layers.validation.eval_sampler import select_eval_sample
from layers.validation.eval_cache import build_governance_summary


def _make_incident(
    incident_id: str,
    severity: str = "P3",
    *,
    deployment_notes: str | None = None,
    title: str = "Incident",
    signals: list[str] | None = None,
    true_root_cause: str | None = None,
) -> UnifiedIncident:
    return UnifiedIncident(
        incident_id=incident_id,
        title=title,
        description=f"Description for {incident_id}",
        severity=severity,
        affected_system="svc",
        signals=signals or ["ERROR svc: timeout"],
        deployment_notes=deployment_notes,
        source_dataset="synthetic",
        true_root_cause=true_root_cause,
    )


def test_select_eval_sample_caps_at_n():
    pool = [
        _make_incident(f"SYN-{i:03d}", severity=["P1", "P2", "P3", "P4"][i % 4])
        for i in range(20)
    ]
    sample = select_eval_sample(pool, n=5, seed=42)
    assert len(sample) == 5
    assert len({s.incident_id for s in sample}) == 5


def test_select_eval_sample_returns_all_when_pool_small():
    pool = [_make_incident("A"), _make_incident("B")]
    assert len(select_eval_sample(pool, n=5)) == 2


def test_label_alignment_score_overlap():
    score = label_alignment_score(
        "Connection pool exhaustion in deployment",
        "pool exhaustion caused by misconfigured deployment",
    )
    assert score > 0.0


def test_label_alignment_score_empty_true():
    assert label_alignment_score("something", "") == 0.0


def test_eval_cache_roundtrip(tmp_path, sample_incident, sample_rca):
    settings = Settings(groq_model="test-model")
    phash = compute_prompt_hash(settings)
    cache_path = tmp_path / "cache.json"
    cache = EvalCache(str(cache_path), phash)
    from layers.validation.validator import RCAValidator

    validation = RCAValidator().validate_live(sample_rca, sample_incident)
    cache.put(sample_incident, sample_rca, validation, [], reasoning_ms=100)
    cache.save()

    cache2 = EvalCache(str(cache_path), phash)
    row = cache2.get(sample_incident.incident_id)
    assert row is not None
    assert row.probable_root_cause == sample_rca.probable_root_cause
    assert row.trust_badge in ("PASS", "FLAG", "FAIL")


def test_eval_cache_invalidates_on_prompt_hash_change(tmp_path, sample_incident, sample_rca):
    cache_path = tmp_path / "cache.json"
    cache = EvalCache(str(cache_path), "hash_a")
    from layers.validation.validator import RCAValidator

    validation = RCAValidator().validate_live(sample_rca, sample_incident)
    cache.put(sample_incident, sample_rca, validation, [], reasoning_ms=50)
    cache.save()

    cache_b = EvalCache(str(cache_path), "hash_b")
    assert cache_b.get(sample_incident.incident_id) is None


def test_build_governance_summary_metrics(sample_incident, sample_rca):
    settings = Settings(groq_model="test-model")
    cache = EvalCache(str(Path("unused")), compute_prompt_hash(settings))
    from layers.validation.validator import RCAValidator

    validation = RCAValidator().validate_live(sample_rca, sample_incident)
    cache.put(sample_incident, sample_rca, validation, [], reasoning_ms=200)

    summary = build_governance_summary(
        [sample_incident],
        cache,
        pool_size=50,
        new_llm_runs=1,
        suite_passed=True,
    )
    assert summary["eval_sample_size"] == 1
    assert summary["estimated_groq_calls"] == 1
    assert 0.0 <= summary["trust_pass_rate"] <= 1.0
    assert summary["giskard_suite_passed"] is True
