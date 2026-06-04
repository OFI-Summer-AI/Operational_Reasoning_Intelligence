from pydantic import BaseModel, Field


class RCAOutput(BaseModel):
    """Structured output from the reasoning layer."""

    probable_root_cause: str
    confidence: int = Field(ge=0, le=100)
    affected_components: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    similar_incident_ids: list[str] = Field(default_factory=list)
    reasoning_trace: str = ""
    model_used: str = ""
    latency_ms: int = 0
