"""Governance evaluation: sample → cache RCA → Giskard suite (minimal LLM spend)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import structlog

from config.settings import Settings
from layers.ingestion.schema import UnifiedIncident
from layers.memory.vector_store import IncidentVectorStore
from layers.reasoning.chain import RCAChain
from layers.validation.eval_cache import EvalCache, build_governance_summary, compute_prompt_hash
from layers.validation.eval_sampler import select_eval_sample
from layers.validation.giskard_model import create_cache_backed_giskard_model
from layers.validation.test_suite import build_giskard_dataset, run_governance_checks
from layers.validation.validator import RCAValidator

logger = structlog.get_logger(__name__)


def _resolve_governance_cache_path(settings: Settings) -> str:
    """Prefer data/governance/; fall back to legacy data/eval/."""
    primary = Path(settings.governance_cache_path)
    if primary.exists():
        return str(primary)
    for legacy in (
        Path("./data/eval/rca_predictions.json"),
        Path(settings.governance_cache_path.replace("governance", "eval")),
    ):
        if legacy.exists():
            return str(legacy)
    return str(primary)


async def warm_eval_predictions(
    incidents: list[UnifiedIncident],
    settings: Settings,
    cache: EvalCache,
    *,
    reuse_cache: bool,
    force_fresh: bool,
) -> int:
    """
    Run production-like RCA (ChromaDB top-3 + Groq) for sampled incidents only.
    Returns number of new LLM-backed RCA runs (each = 1 Groq call).
    """
    store = IncidentVectorStore(
        persist_dir=settings.chromadb_persist_dir,
        collection_name=settings.chromadb_collection_name,
        embedding_model=settings.embedding_model,
        embedding_cache_dir=settings.embedding_cache_dir,
    )
    chain = RCAChain(settings)
    validator = RCAValidator()
    new_runs = 0

    for incident in incidents:
        if reuse_cache and not force_fresh and cache.get(incident.incident_id):
            logger.info("governance.cache_hit", incident_id=incident.incident_id)
            continue

        t0 = time.monotonic()
        query = f"{incident.title} {incident.description} {' '.join(incident.signals[:3])}"
        similar = store.similarity_search(query, k=3)
        rca = await chain.run(incident, similar)
        validation = validator.validate_live(rca, incident)
        reasoning_ms = int((time.monotonic() - t0) * 1000)
        cache.put(incident, rca, validation, similar, reasoning_ms)
        new_runs += 1
        logger.info(
            "governance.rca_cached",
            incident_id=incident.incident_id,
            badge=validation.giskard_badge,
            reasoning_ms=reasoning_ms,
            similar_count=len(similar),
        )

    cache.save()
    return new_runs


def _write_html_report(
    report_dir: Path,
    summary: dict[str, Any],
    suite_results: Any | None,
    scan_html_path: str | None,
) -> str:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "governance_report.html"
    suite_block = ""
    if suite_results is not None:
        suite_block = f"<pre>{json.dumps(suite_results, indent=2, default=str)}</pre>"
    scan_link = ""
    if scan_html_path:
        scan_link = f'<p>Full scan: <a href="{Path(scan_html_path).name}">giskard_scan.html</a></p>'

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>ORI Governance Report</title></head>
<body>
<h1>ORI Governance &amp; Trust Evaluation</h1>
<p>Sampled {summary['eval_sample_size']} incidents from pool of {summary['eval_pool_size']}.
New LLM RCA runs: {summary['new_llm_rca_runs']} (~{summary['estimated_groq_calls']} Groq calls).</p>
<h2>Business KPIs vs targets</h2>
<p><em>Trust assessment measures risk (grounding/hallucination), not guaranteed correctness.</em></p>
<table border="1" cellpadding="6">
<tr><th>KPI</th><th>Target</th><th>Observed (sample)</th><th>Met?</th></tr>
{"".join(
    f"<tr><td>{r['kpi']}</td><td>{r['target']}</td><td>{r['observed']}</td>"
    f"<td>{'✓' if r.get('met') is True else ('✗' if r.get('met') is False else '—')}</td></tr>"
    for r in summary.get("business_kpis", [])
)}
</table>
<h2>Sample metrics</h2>
<ul>
<li>Trust pass rate (risk tier PASS): {summary['trust_pass_rate']}</li>
<li>Hallucination rate: {summary['hallucination_rate']}</li>
<li>Mean grounding score: {summary['mean_grounding_score']}</li>
<li>Mean label alignment: {summary['mean_label_alignment']}</li>
<li>Mean reasoning ms: {summary['mean_reasoning_ms']}</li>
<li>Giskard suite passed: {summary['giskard_suite_passed']}</li>
</ul>
{scan_link}
<h2>Suite results</h2>
{suite_block}
<h2>Per-incident</h2>
<pre>{json.dumps(summary.get('incidents', []), indent=2)}</pre>
</body></html>"""
    path.write_text(html, encoding="utf-8")
    return str(path)


async def run_governance_evaluation(
    settings: Settings,
    *,
    eval_samples: int | None = None,
    force_fresh: bool = False,
) -> dict[str, Any]:
    """
    Governance path: stratified sample → warm cache (LLM) → Giskard suite on cache-backed model.
    """
    if not settings.giskard_scan_enabled:
        logger.info("governance.disabled", reason="GISKARD_SCAN_ENABLED=false")
        return {"status": "disabled"}

    synthetic_path = Path(settings.synthetic_data_path)
    if not synthetic_path.exists():
        raise FileNotFoundError(
            f"Synthetic pool missing: {synthetic_path}. Run: python main.py --mode generate-synthetic"
        )

    pool_raw = json.loads(synthetic_path.read_text(encoding="utf-8"))
    pool = [UnifiedIncident(**r) for r in pool_raw[: settings.giskard_eval_pool_size]]
    n = eval_samples if eval_samples is not None else settings.giskard_eval_sample_size
    sampled = select_eval_sample(pool, n=n, seed=settings.giskard_eval_seed)
    logger.info(
        "governance.sampled",
        pool_size=len(pool),
        sample_size=len(sampled),
        incident_ids=[i.incident_id for i in sampled],
    )

    prompt_hash = compute_prompt_hash(settings)
    cache_path = _resolve_governance_cache_path(settings)
    cache = EvalCache(cache_path, prompt_hash)
    new_runs = await warm_eval_predictions(
        sampled,
        settings,
        cache,
        reuse_cache=settings.giskard_reuse_cache,
        force_fresh=force_fresh,
    )

    giskard_model = create_cache_backed_giskard_model(cache, sampled)
    giskard_dataset = build_giskard_dataset(sampled)

    validator = RCAValidator()
    check_results = run_governance_checks(giskard_model, giskard_dataset)
    suite_passed = check_results.get("passed")
    suite_results = check_results

    report_dir = Path(settings.giskard_eval_report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    giskard_scan_path = report_dir / "giskard_scan.html"

    # Primary Giskard deliverable for EM / UI (official scan HTML)
    if settings.giskard_use_full_scan:
        logger.info("governance.giskard_scan_start")
        try:
            scan_result = validator.run_giskard_scan(giskard_model, giskard_dataset)
            scan_result.to_html(str(giskard_scan_path))
            logger.info("governance.giskard_scan_saved", path=str(giskard_scan_path))
        except Exception as e:
            logger.warning("governance.giskard_scan_failed", error=str(e))

    summary = build_governance_summary(
        sampled,
        cache,
        pool_size=len(pool),
        new_llm_runs=new_runs,
        suite_passed=suite_passed,
    )
    summary["giskard_scan_html"] = str(giskard_scan_path) if giskard_scan_path.exists() else None
    summary["giskard_library"] = (
        "giskard.scan" if settings.giskard_use_full_scan else "custom_checks_only"
    )
    summary["scan_mode"] = settings.effective_giskard_mode

    summary_path = report_dir / "governance_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    html_path = _write_html_report(report_dir, summary, suite_results, str(giskard_scan_path) if giskard_scan_path.exists() else None)
    logger.info(
        "governance.complete",
        summary_path=str(summary_path),
        giskard_scan_path=str(giskard_scan_path) if giskard_scan_path.exists() else None,
        html_path=html_path,
        new_llm_runs=new_runs,
        **{k: summary[k] for k in ("trust_pass_rate", "hallucination_rate")},
    )
    return {
        "summary": summary,
        "summary_path": str(summary_path),
        "html_path": html_path,
        "giskard_scan_path": str(giskard_scan_path) if giskard_scan_path.exists() else None,
    }

