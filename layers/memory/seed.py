"""Raw → unified JSON (processed/) → ChromaDB."""
import json
from pathlib import Path

import structlog

from layers.ingestion.normaliser import normalise_batch
from layers.ingestion.parsers import parse_csv, parse_json, parse_log_lines
from layers.ingestion.schema import UnifiedIncident
from layers.memory.vector_store import IncidentVectorStore

logger = structlog.get_logger(__name__)


def process_raw_to_unified(
    raw_dir: str | Path,
    processed_dir: str | Path,
    *,
    synthetic_path: str | Path | None = None,
) -> int:
    """Parse files under raw/ into UnifiedIncident JSON under processed/."""
    raw_path = Path(raw_dir)
    out_path = Path(processed_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    total = 0

    for path in raw_path.glob("pag_incidents.*"):
        records = parse_csv(path) if path.suffix == ".csv" else parse_json(path)
        incidents = normalise_batch(records, "pag")
        (out_path / "pag_incidents.json").write_text(
            json.dumps([i.model_dump(mode="json") for i in incidents], default=str)
        )
        total += len(incidents)

    for path in raw_path.glob("it_incidents.*"):
        records = parse_csv(path) if path.suffix == ".csv" else parse_json(path)
        incidents = normalise_batch(records, "it_incidents")
        (out_path / "it_incidents.json").write_text(
            json.dumps([i.model_dump(mode="json") for i in incidents], default=str)
        )
        total += len(incidents)

    hdfs_dir = raw_path / "hdfs_logs"
    if hdfs_dir.exists():
        all_logs = []
        for log_file in hdfs_dir.glob("*.log"):
            all_logs.extend(parse_log_lines(log_file))
        incidents = normalise_batch(all_logs, "hdfs_logs")
        (out_path / "hdfs_logs.json").write_text(
            json.dumps([i.model_dump(mode="json") for i in incidents], default=str)
        )
        total += len(incidents)

    synth = Path(synthetic_path or "./data/synthetic/synthetic_incidents.json")
    if synth.exists():
        records = parse_json(synth)
        incidents = normalise_batch(records, "synthetic")
        (out_path / "synthetic.json").write_text(
            json.dumps([i.model_dump(mode="json") for i in incidents], default=str)
        )
        total += len(incidents)

    logger.info("seed.processed_raw", total_records=total, processed_dir=str(out_path))
    return total


def load_processed_incidents(processed_dir: str) -> list[UnifiedIncident]:
    processed_path = Path(processed_dir)
    incidents: list[UnifiedIncident] = []
    if not processed_path.exists():
        return incidents
    for json_file in sorted(processed_path.glob("*.json")):
        try:
            records = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(records, dict):
                records = [records]
            for r in records:
                try:
                    incidents.append(UnifiedIncident(**r))
                except Exception as e:
                    logger.warning("seed.skip_record", file=json_file.name, error=str(e))
            logger.info("seed.loaded_file", file=json_file.name, count=len(records))
        except Exception as e:
            logger.error("seed.file_failed", file=str(json_file), error=str(e), exc_info=True)
    return incidents


def seed_chromadb(
    processed_dir: str,
    persist_dir: str,
    collection_name: str,
    embedding_model: str = "all-MiniLM-L6-v2",
    embedding_cache_dir: str = "./data/embedding_cache",
    batch_size: int = 100,
    dry_run: bool = False,
) -> int:
    incidents = load_processed_incidents(processed_dir)
    if not incidents:
        logger.warning("seed.no_incidents_found", processed_dir=processed_dir)
        return 0

    store = IncidentVectorStore(
        persist_dir=persist_dir,
        collection_name=collection_name,
        embedding_model=embedding_model,
        embedding_cache_dir=embedding_cache_dir,
    )
    before = store.count()
    logger.info("seed.start", total_incidents=len(incidents), existing_in_db=before, dry_run=dry_run)

    if dry_run:
        logger.info("seed.dry_run", would_upsert=len(incidents))
        return len(incidents)

    for i in range(0, len(incidents), batch_size):
        store.upsert(incidents[i : i + batch_size])

    after = store.count()
    logger.info("seed.complete", seeded=len(incidents), db_before=before, db_after=after)
    return len(incidents)
