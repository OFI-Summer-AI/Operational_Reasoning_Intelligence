"""Enrich RCA next steps using ChromaDB retrieval (no extra LLM calls)."""
from __future__ import annotations

from layers.ingestion.schema import SimilarIncident
from layers.ingestion.text_utils import normalize_unicode_text
from layers.reasoning.rca_output import RCAOutput


def enrich_next_steps_from_vector(
    rca: RCAOutput,
    similar: list[SimilarIncident],
    *,
    store_count: int,
) -> list[str]:
    steps = list(rca.next_steps)
    seen = {s.strip().lower() for s in steps}

    if similar:
        top = similar[0]
        hint = (
            f"Compare with historical incident [{top.incident_id}] "
            f"({normalize_unicode_text(top.title)}, similarity={top.similarity_score:.2f})"
        )
        if hint.lower() not in seen:
            steps.append(hint)
        if len(similar) > 1:
            ids = ", ".join(s.incident_id for s in similar[1:3])
            steps.append(f"Review additional similar cases: {ids}")
    elif store_count == 0:
        msg = "Seed the incident repository (python main.py --mode seed) for historical context"
        if msg.lower() not in seen:
            steps.append(msg)
    else:
        msg = "No similar incidents above threshold — broaden signal keywords or add history"
        if msg.lower() not in seen:
            steps.append(msg)

    return steps
