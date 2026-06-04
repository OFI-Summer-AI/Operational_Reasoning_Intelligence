"""Shared pytest fixtures."""
import pytest
from layers.ingestion.schema import UnifiedIncident, SimilarIncident
from layers.reasoning.rca_output import RCAOutput
from layers.validation.validator import ValidationResult


@pytest.fixture
def sample_incident() -> UnifiedIncident:
    return UnifiedIncident(
        incident_id="TEST-001",
        title="Database Connection Pool Exhausted",
        description="All API requests failing due to DB connection pool exhaustion.",
        severity="P1",
        affected_system="api-service",
        signals=[
            "ERROR api-service: connection pool exhausted (pool_size=10, waiting=25)",
            "ERROR postgres-primary: max_connections exceeded",
            "WARN deployment: api-service v1.2.3 deployed 5 minutes ago",
        ],
        deployment_notes="api-service v1.2.3 deployed with updated pool_size config",
        source_dataset="test",
    )


@pytest.fixture
def sample_rca() -> RCAOutput:
    return RCAOutput(
        probable_root_cause="Connection pool exhaustion caused by misconfigured pool_size in deployment",
        confidence=85,
        affected_components=["api-service", "postgres-primary"],
        evidence=[
            "connection pool exhausted (pool_size=10, waiting=25)",
            "max_connections exceeded on postgres-primary",
        ],
        next_steps=[
            "Rollback api-service to v1.2.2",
            "Increase pool_size to 50 in config",
            "Restart api-service pods",
        ],
        similar_incident_ids=["HIST-045", "HIST-078"],
        model_used="llama-3.3-70b-versatile",
        latency_ms=2500,
    )


@pytest.fixture
def sample_similar_incidents() -> list[SimilarIncident]:
    return [
        SimilarIncident(
            incident_id="HIST-045",
            title="API Connection Pool Exhausted",
            description="Similar DB pool issue from 3 months ago",
            root_cause="Misconfigured pool_size after deployment",
            similarity_score=0.91,
            source_dataset="pag",
        )
    ]
