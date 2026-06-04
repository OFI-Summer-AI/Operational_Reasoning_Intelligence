"""UI/API startup: ingestion regression + auto-seed ChromaDB when empty."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from config.settings import Settings
from layers.ingestion.input_validation import InputValidationSummary, run_all_input_validation_tests
from layers.ingestion.schema import UnifiedIncident
from layers.memory.vector_store import IncidentVectorStore

logger = structlog.get_logger(__name__)


def ensure_vector_memory(settings: Settings) -> dict[str, Any]:
    """Seed ChromaDB from processed/ or synthetic pool if empty."""
    store = IncidentVectorStore(
        persist_dir=settings.chromadb_persist_dir,
        collection_name=settings.chromadb_collection_name,
        embedding_model=settings.embedding_model,
        embedding_cache_dir=settings.embedding_cache_dir,
    )
    before = store.count()
    if before > 0:
        return {
            "seeded": 0,
            "count": before,
            "source": "existing",
            "collection": settings.chromadb_collection_name,
        }

    processed = Path(settings.processed_data_dir)
    incidents: list[UnifiedIncident] = []
    source = "none"

    if processed.exists():
        from layers.memory.seed import load_processed_incidents

        incidents = load_processed_incidents(str(processed))
        source = "processed"

    if not incidents:
        synth_path = Path(settings.synthetic_data_path)
        if synth_path.exists():
            raw = json.loads(synth_path.read_text(encoding="utf-8"))
            incidents = [UnifiedIncident(**r) for r in raw]
            source = "synthetic"

    if not incidents:
        return {
            "seeded": 0,
            "count": 0,
            "source": "none",
            "message": "No data to seed",
            "collection": settings.chromadb_collection_name,
        }

    store.upsert(incidents)
    after = store.count()
    logger.info("demo.seed_done", source=source, count=after)
    return {
        "seeded": len(incidents),
        "count": after,
        "source": source,
        "collection": settings.chromadb_collection_name,
    }


async def run_startup_checks(settings: Settings) -> dict[str, Any]:
    """Ingestion regression + vector store — once per UI session."""
    qa: InputValidationSummary = run_all_input_validation_tests(
        settings.input_validation_cases_path
    )
    memory = ensure_vector_memory(settings)
    return {
        "input_validation": qa.model_dump(),
        "memory": memory,
        "ready": qa.failed == 0,
    }
