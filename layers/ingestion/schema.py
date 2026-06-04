from datetime import datetime
from typing import Literal
import uuid
from pydantic import BaseModel, Field


class UnifiedIncident(BaseModel):
    """Canonical incident schema used across all layers."""

    incident_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    severity: Literal["P1", "P2", "P3", "P4"] = "P3"
    affected_system: str = "unknown"
    signals: list[str] = Field(default_factory=list)
    deployment_notes: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source_dataset: str = "unknown"
    true_root_cause: str | None = None
    raw_text: str = ""


class SimilarIncident(BaseModel):
    """A retrieved similar incident with its similarity score."""

    incident_id: str
    title: str
    description: str
    root_cause: str | None = None
    similarity_score: float
    source_dataset: str = "unknown"
