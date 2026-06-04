"""Validate incident form/API payloads before Groq runs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import structlog
from pydantic import BaseModel, Field

from layers.ingestion.normaliser import normalise
from layers.ingestion.schema import UnifiedIncident

logger = structlog.get_logger(__name__)

ExpectOutcome = Literal["pass", "fail"]


class InputValidationResult(BaseModel):
    case_id: str
    name: str
    passed: bool
    expect: ExpectOutcome
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    incident_id: str | None = None


class InputValidationSummary(BaseModel):
    total: int
    passed: int
    failed: int
    results: list[InputValidationResult]


def _signal_text(raw: dict[str, Any]) -> str:
    sig = raw.get("signals") or raw.get("alerts") or raw.get("logs") or []
    if isinstance(sig, list):
        return " ".join(str(s) for s in sig if s)
    return str(sig) if sig else ""


def validate_user_input(
    raw: Any, *, source_dataset: str = "user_input"
) -> tuple[UnifiedIncident | None, list[str], list[str]]:
    """Gate before LLM spend. Returns (incident, errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(raw, dict):
        return None, ["Input must be a JSON object (incident fields)."], warnings

    title = str(raw.get("title") or raw.get("name") or "").strip()
    description = str(raw.get("description") or raw.get("desc") or "").strip()
    signal_blob = _signal_text(raw).strip()

    if not title and not description:
        errors.append("Provide at least a title or description.")

    if not signal_blob and not description:
        errors.append("No operational signals: add signals or a non-empty description.")
    elif not signal_blob and description:
        warnings.append("No explicit signals; description will be used as minimal signal context.")

    if not str(raw.get("affected_system") or raw.get("system") or "").strip():
        warnings.append("affected_system missing — defaulting to 'unknown'.")

    if errors:
        return None, errors, warnings

    incident = normalise(raw, source_dataset=source_dataset)
    if incident is None:
        errors.append("Normalisation failed — check field types and lengths.")
        return None, errors, warnings

    if len(incident.signals) < 1:
        errors.append("No operational signals after normalisation.")
        return None, errors, warnings

    return incident, errors, warnings


def run_validation_case(case: dict[str, Any]) -> InputValidationResult:
    case_id = str(case.get("case_id", "unknown"))
    name = str(case.get("name", case_id))
    expect: ExpectOutcome = case.get("expect", "pass")  # type: ignore[assignment]
    raw = case.get("input")
    expect_fragments: list[str] = case.get("expect_error_contains") or []

    if not isinstance(raw, dict):
        _, errors, _ = validate_user_input(raw)
    else:
        _, errors, _ = validate_user_input(raw, source_dataset="validation_test")

    if expect == "pass":
        passed = len(errors) == 0
    else:
        passed = len(errors) > 0
        if passed and expect_fragments:
            blob = " ".join(errors).lower()
            passed = all(f.lower() in blob for f in expect_fragments)

    incident_id = None
    if isinstance(raw, dict) and not errors:
        inc = normalise(raw, source_dataset="validation_test")
        incident_id = inc.incident_id if inc else None

    return InputValidationResult(
        case_id=case_id,
        name=name,
        passed=passed,
        expect=expect,
        errors=errors,
        incident_id=incident_id,
    )


def _resolve_cases_path(path: str | Path | None) -> Path:
    if path is None:
        path = Path(__file__).resolve().parents[2] / "testcases" / "input_validation.json"
    p = Path(path)
    if p.exists():
        return p
    for alt in (
        "input_validation.json",
        "ingestion_regression.json",
        "ingestion_cases.json",
    ):
        for base in (p.parent, Path(__file__).resolve().parents[2] / "testcases"):
            candidate = base / alt
            if candidate.exists():
                return candidate
    raise FileNotFoundError(f"Input validation cases not found: {path}")


def load_validation_cases(path: str | Path | None = None) -> list[dict[str, Any]]:
    p = _resolve_cases_path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{p.name} must be a JSON array")
    return data


def run_all_input_validation_tests(path: str | Path | None = None) -> InputValidationSummary:
    cases = load_validation_cases(path)
    results = [run_validation_case(c) for c in cases]
    passed = sum(1 for r in results if r.passed)
    logger.info("input_validation.complete", total=len(results), passed=passed)
    return InputValidationSummary(
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        results=results,
    )
