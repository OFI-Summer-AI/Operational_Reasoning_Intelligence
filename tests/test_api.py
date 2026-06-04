"""Tests for the FastAPI layer."""
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ORI"


def test_analyze_incident_missing_body(client):
    response = client.post("/api/incidents/analyze", json={"description": "something"})
    assert response.status_code == 422


def test_analyze_incident_minimal_body(client):
    """Enterprise pipeline mocked — no Groq."""
    incident = {
        "title": "Test Incident",
        "description": "Something broke",
        "severity": "P2",
        "affected_system": "test-service",
        "signals": ["ERROR test-service: connection refused"],
    }

    mock_result = {
        "incident_id": "TEST-API",
        "timestamp": datetime.utcnow().isoformat(),
        "probable_root_cause": "Test root cause",
        "confidence": 75,
        "affected_components": ["test-service"],
        "evidence": ["connection refused"],
        "next_steps": ["restart service"],
        "similar_incidents": [],
        "giskard_badge": "PASS",
        "validation_issues": [],
        "hallucination_detected": False,
        "grounding_score": 0.9,
        "model_used": "llama-test",
        "total_latency_ms": 100,
        "pipeline_trace": {"scan_mode": "live_trust"},
    }

    with patch(
        "api.routes.incidents.run_enterprise_rca",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = client.post("/api/incidents/analyze", json=incident)

    assert response.status_code == 200
    data = response.json()
    assert "probable_root_cause" in data
    assert "giskard_badge" in data


def test_get_history_empty(client):
    response = client.get("/api/incidents/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
