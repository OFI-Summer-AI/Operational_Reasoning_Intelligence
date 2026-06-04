"""Tests for the ingestion layer."""
import json
import tempfile
from pathlib import Path

import pytest
from layers.ingestion.parsers import parse_csv, parse_json, parse_log_lines, parse_markdown
from layers.ingestion.normaliser import normalise, normalise_batch
from layers.ingestion.schema import UnifiedIncident


def test_parse_json_list(tmp_path):
    data = [{"title": "Test", "description": "desc", "severity": "P1"}]
    f = tmp_path / "test.json"
    f.write_text(json.dumps(data))
    result = parse_json(f)
    assert len(result) == 1
    assert result[0]["title"] == "Test"


def test_parse_json_object(tmp_path):
    data = {"title": "Test", "description": "desc"}
    f = tmp_path / "test.json"
    f.write_text(json.dumps(data))
    result = parse_json(f)
    assert len(result) == 1


def test_parse_csv(tmp_path):
    csv_content = "title,description,severity\nDB Down,Database offline,P1\nNetwork Slow,High latency,P2"
    f = tmp_path / "test.csv"
    f.write_text(csv_content)
    result = parse_csv(f)
    assert len(result) == 2
    assert result[0]["title"] == "DB Down"


def test_parse_log_lines(tmp_path):
    logs = "INFO 12:00 all good\nERROR 12:01 database failed\nWARN 12:02 high memory\nDEBUG stuff"
    f = tmp_path / "test.log"
    f.write_text(logs)
    result = parse_log_lines(f)
    assert len(result) == 1
    assert len(result[0]["signals"]) == 2  # ERROR + WARN


def test_parse_markdown(tmp_path):
    md = "# Incident Report\n\n## Summary\nDatabase went down.\n\n## Root Cause\nDisk full."
    f = tmp_path / "incident.md"
    f.write_text(md)
    result = parse_markdown(f)
    assert len(result) == 1
    assert "disk full" in result[0]["true_root_cause"].lower()


def test_normalise_minimal():
    raw = {"title": "Test Incident", "description": "Something broke"}
    incident = normalise(raw)
    assert incident is not None
    assert incident.title == "Test Incident"
    assert incident.severity == "P3"  # default


def test_normalise_severity_coercion():
    raw = {"title": "Crit", "description": "bad", "severity": "critical"}
    incident = normalise(raw)
    assert incident.severity == "P1"


def test_normalise_missing_required_graceful():
    raw = {}
    incident = normalise(raw)
    assert incident is not None
    assert incident.title == "Untitled Incident"


def test_normalise_batch():
    records = [
        {"title": f"Incident {i}", "description": f"desc {i}"} for i in range(5)
    ]
    incidents = normalise_batch(records, "test")
    assert len(incidents) == 5
    assert all(isinstance(i, UnifiedIncident) for i in incidents)


def test_unified_incident_model(sample_incident):
    assert sample_incident.incident_id == "TEST-001"
    assert sample_incident.severity == "P1"
    assert len(sample_incident.signals) == 3
