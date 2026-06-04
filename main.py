"""
ORI — Main entry point

First-time setup (in order):
  1. pip install -r requirements.txt
  2. copy .env.example .env  → set GROQ_API_KEY
  3. python main.py --mode validate-input
  4. python datasets/download.py
  5. python main.py --mode seed
  6. python main.py --mode ui

Modes:
  python main.py                                          # RCA on sample incident (1 Groq call)
  python main.py --incident-file path/to/incident.json    # RCA on custom JSON
  python main.py --mode ui                                # Streamlit console (recommended demo)
  python main.py --mode api                               # FastAPI server
  python main.py --mode seed                              # raw → processed → ChromaDB
  python main.py --mode seed --dry-run                    # Preview seed (no ChromaDB write)
  python main.py --mode validate-input                    # Input gate tests (no API key)
  python main.py --mode generate-synthetic                # Optional eval pool (uses Groq)
  python main.py --mode giskard-scan                      # Batch trust eval (sample, default 5)
  python main.py --mode giskard-scan --eval-samples 5 --eval-fresh
  python main.py --mode test                              # Run pytest
"""
import argparse
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import structlog


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ORI Operational Reasoning Intelligence Platform")
    parser.add_argument(
        "--mode",
        choices=[
            "run",
            "api",
            "ui",
            "seed",
            "giskard-scan",
            "validate-input",
            "generate-synthetic",
            "test",
        ],
        default="run",
    )
    parser.add_argument("--incident-file", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--n-synthetic", type=int, default=50)
    parser.add_argument(
        "--eval-samples",
        type=int,
        default=None,
        help="Governance eval sample size (default: GISKARD_EVAL_SAMPLE_SIZE, usually 5)",
    )
    parser.add_argument(
        "--eval-fresh",
        action="store_true",
        help="Ignore governance prediction cache and re-run Groq RCA on samples",
    )
    return parser.parse_args()


async def run_single_incident(
    incident_file: str | None,
    settings,
    logger: structlog.BoundLogger,
) -> None:
    """Run the enterprise ORI pipeline on one incident."""
    from layers.ingestion.parsers import parse_json
    from layers.pipeline.enterprise import run_enterprise_rca
    from layers.output.formatter import to_terminal
    from layers.output.report import RCAReport

    # Default to sample incident
    if not incident_file:
        incident_file = "./data/synthetic/sample_incident.json"

    if not Path(incident_file).exists():
        logger.error("main.incident_file_missing", path=incident_file)
        sys.exit(1)

    records = parse_json(incident_file)
    raw = records[0] if records else {}
    result = await run_enterprise_rca(raw, settings, source_dataset="cli")

    if result.get("error"):
        logger.error("main.pipeline_failed", error=result["error"], file=incident_file)
        sys.exit(1)

    report = RCAReport.model_validate(
        {k: v for k, v in result.items() if k in RCAReport.model_fields}
    )
    print(to_terminal(report))

    reports_dir = Path(settings.giskard_eval_report_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    safe_id = report.incident_id.replace("/", "-")
    report_path = reports_dir / f"live_{safe_id}.json"
    report_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    trace = result.get("pipeline_trace") or {}
    logger.info(
        "main.complete",
        incident_id=report.incident_id,
        badge=report.giskard_badge,
        report_path=str(report_path),
        log_file=settings.log_file,
        scan_mode=trace.get("scan_mode", "live_trust"),
        **{k: trace[k] for k in trace if k.endswith("_ms") or k in ("similar_count", "total_ms")},
    )
    print(f"\n  Report saved: {report_path}")
    print(f"  Logs:         {settings.log_file}\n")


async def seed_database(settings, logger: structlog.BoundLogger, dry_run: bool = False) -> None:
    from layers.memory.seed import process_raw_to_unified, seed_chromadb

    n_processed = process_raw_to_unified(
        settings.raw_data_dir,
        settings.processed_data_dir,
        synthetic_path=settings.synthetic_data_path,
    )
    logger.info("seed.unified_records", count=n_processed, dir=settings.processed_data_dir)

    count = seed_chromadb(
        processed_dir=settings.processed_data_dir,
        persist_dir=settings.chromadb_persist_dir,
        collection_name=settings.chromadb_collection_name,
        embedding_model=settings.embedding_model,
        embedding_cache_dir=settings.embedding_cache_dir,
        dry_run=dry_run,
    )
    logger.info("seed.done", seeded=count, dry_run=dry_run)


async def run_giskard_scan(
    settings,
    logger: structlog.BoundLogger,
    *,
    eval_samples: int | None = None,
    force_fresh: bool = False,
) -> None:
    from layers.validation.governance import run_governance_evaluation

    try:
        result = await run_governance_evaluation(
            settings,
            eval_samples=eval_samples,
            force_fresh=force_fresh,
        )
    except FileNotFoundError as e:
        logger.error("giskard_scan.missing_synthetic", error=str(e))
        logger.info("giskard_scan.hint", msg="Run: python main.py --mode generate-synthetic")
        sys.exit(1)

    if result.get("status") == "disabled":
        logger.info("giskard_scan.skipped", reason="GISKARD_SCAN_ENABLED=false")
        return

    logger.info(
        "giskard_scan.done",
        summary_path=result.get("summary_path"),
        giskard_scan_path=result.get("giskard_scan_path"),
        html_path=result.get("html_path"),
    )


async def generate_synthetic(settings, logger: structlog.BoundLogger, n: int = 50) -> None:
    from layers.ingestion.synthetic_generator import generate_synthetic_incidents

    incidents = await generate_synthetic_incidents(
        n=n,
        output_path=settings.synthetic_data_path,
        model=settings.groq_model,
        api_key=settings.groq_api_key,
    )
    logger.info("synthetic.done", generated=len(incidents))


def run_api_server(settings) -> None:
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
    )


def run_streamlit() -> None:
    """OFI UI — paste incident fields; pipeline logs print in this terminal."""
    print("\n  ORI UI — watch this terminal for pipeline logs (structlog INFO)\n")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "frontend/streamlit_app.py",
            "--server.headless",
            "true",
        ],
        check=True,
    )


def run_tests() -> None:
    subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"], check=False)


async def main() -> None:
    args = parse_args()

    from config.settings import get_settings
    from config.logging_config import setup_logging

    settings = get_settings()
    logger = setup_logging(
        log_level=settings.log_level,
        log_format=settings.log_format,
        log_file=settings.log_file,
    )
    logger.info("ori.start", mode=args.mode)

    if args.mode == "run":
        await run_single_incident(args.incident_file, settings, logger)
    elif args.mode == "api":
        run_api_server(settings)
    elif args.mode == "ui":
        run_streamlit()
    elif args.mode == "seed":
        await seed_database(settings, logger, dry_run=args.dry_run)
    elif args.mode == "giskard-scan":
        await run_giskard_scan(
            settings,
            logger,
            eval_samples=args.eval_samples,
            force_fresh=args.eval_fresh,
        )
    elif args.mode == "validate-input":
        from layers.ingestion.input_validation import run_all_input_validation_tests

        summary = run_all_input_validation_tests(settings.input_validation_cases_path)
        logger.info(
            "validate_input.done",
            passed=summary.passed,
            failed=summary.failed,
            total=summary.total,
        )
        for r in summary.results:
            status = "PASS" if r.passed else "FAIL"
            print(f"  [{status}] {r.case_id} {r.name}")
        if summary.failed:
            sys.exit(1)
    elif args.mode == "generate-synthetic":
        await generate_synthetic(settings, logger, n=args.n_synthetic)
    elif args.mode == "test":
        run_tests()


if __name__ == "__main__":
    asyncio.run(main())
