"""Context enrichment and report validation (no Groq)."""
from layers.pipeline.context_enrichment import enrich_next_steps_from_vector
from layers.validation.report_validator import validate_rca_report


def test_validate_rca_report_pass(sample_incident, sample_rca):
    result = validate_rca_report(sample_rca, sample_incident, [])
    assert result.badge in ("PASS", "FLAG", "FAIL")
    assert "probable_root_cause" in result.claims_checked


def test_enrich_next_steps_empty_store(sample_incident, sample_rca):
    steps = enrich_next_steps_from_vector(sample_rca, [], store_count=0)
    assert any("incident repository" in s.lower() for s in steps)


def test_enrich_next_steps_with_similar(sample_incident, sample_rca, sample_similar_incidents):
    steps = enrich_next_steps_from_vector(
        sample_rca, sample_similar_incidents, store_count=5
    )
    assert any("HIST-045" in s for s in steps)
