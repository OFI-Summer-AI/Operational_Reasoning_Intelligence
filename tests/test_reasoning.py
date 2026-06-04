"""Tests for the reasoning layer (no live API calls)."""
import json
import pytest
from layers.reasoning.rca_output import RCAOutput
from layers.reasoning import prompts
from layers.reasoning.chain import RCAChain, _format_signals, _format_similar


def test_rca_output_model(sample_rca):
    assert sample_rca.confidence == 85
    assert len(sample_rca.evidence) == 2
    assert sample_rca.model_used == "llama-3.3-70b-versatile"


def test_rca_output_confidence_bounds():
    with pytest.raises(Exception):
        RCAOutput(probable_root_cause="test", confidence=101)
    with pytest.raises(Exception):
        RCAOutput(probable_root_cause="test", confidence=-1)


def test_format_signals(sample_incident):
    formatted = _format_signals(sample_incident.signals)
    assert "connection pool" in formatted
    assert "•" in formatted


def test_format_signals_empty():
    result = _format_signals([])
    assert "no signals" in result


def test_format_similar(sample_similar_incidents):
    formatted = _format_similar(sample_similar_incidents)
    assert "HIST-045" in formatted
    assert "0.91" in formatted


def test_format_similar_empty():
    result = _format_similar([])
    assert "no similar" in result


def test_prompts_have_placeholders():
    assert "{signals}" in prompts.UNIFIED_RCA_PROMPT
    assert "correlation_summary" in prompts.UNIFIED_RCA_PROMPT
    assert "probable_root_cause" in prompts.UNIFIED_RCA_PROMPT


def test_chain_parse_valid_json():
    """Test RCA JSON parsing without live API."""
    from unittest.mock import MagicMock

    settings = MagicMock()
    settings.groq_api_key = "fake"
    settings.groq_model = "llama-3.3-70b-versatile"
    settings.groq_max_tokens = 4096

    chain = RCAChain.__new__(RCAChain)
    chain.settings = settings

    valid_json = json.dumps({
        "correlation_summary": "trace text",
        "probable_root_cause": "Connection pool exhaustion",
        "confidence": 85,
        "affected_components": ["api-service", "postgres"],
        "evidence": ["connection pool exhausted"],
        "next_steps": ["rollback deployment"],
        "similar_incident_ids": [],
    })
    result = chain._parse_rca(valid_json)
    assert result.confidence == 85
    assert result.probable_root_cause == "Connection pool exhaustion"


def test_chain_parse_invalid_json():
    from unittest.mock import MagicMock

    chain = RCAChain.__new__(RCAChain)
    chain.settings = MagicMock()
    result = chain._parse_rca("not json at all")
    assert result.confidence == 0
    assert "Parse error" in result.probable_root_cause
