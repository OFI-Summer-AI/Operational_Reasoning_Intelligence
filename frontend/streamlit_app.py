"""
ORI — Streamlit UI. Start: python main.py --mode ui
"""
import asyncio
import importlib.util
import html as html_lib
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_ROOT = Path(__file__).resolve().parent.parent
_FRONTEND = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_ofi_theme():
    path = _FRONTEND / "ofi_theme.py"
    spec = importlib.util.spec_from_file_location("ofi_theme", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load theme module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_ofi = _load_ofi_theme()
apply_ofi_theme = _ofi.apply_ofi_theme
ofi_header = _ofi.ofi_header
patch_red = _ofi.patch_red
section_title = _ofi.section_title
results_banner = _ofi.results_banner
display_text = _ofi.display_text

from config.settings import get_settings
from config.logging_config import setup_logging
from layers.pipeline.demo_runner import run_startup_checks
from layers.pipeline.enterprise import run_enterprise_rca
from layers.validation.giskard_ui import GISKARD_ROLE, collect_findings

st.set_page_config(
    page_title="ORI | Operational Reasoning",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

settings = get_settings()
log = setup_logging(settings.log_level, settings.log_format, settings.log_file)
apply_ofi_theme()


def _fmt_latency(ms: int | float) -> str:
    ms = int(ms or 0)
    if ms >= 60_000:
        return f"{ms / 60_000:.1f} min"
    if ms >= 1000:
        return f"{ms / 1000:.1f} s"
    return f"{ms} ms"


def _kpi_row_map(kpis: dict) -> dict[str, dict]:
    return {r["kpi"]: r for r in (kpis.get("kpis") or [])}


def _render_trust_kpis(out: dict) -> None:
    kpis = out.get("trust_kpis") or {}
    if not kpis:
        return
    section_title("Business KPIs")
    st.caption(display_text(kpis.get("disclaimer", "")))

    by_name = _kpi_row_map(kpis)
    highlight = [
        ("RCA draft time", "rca_draft"),
        ("Grounded evidence rate", "grounded"),
        ("Hallucination rate", "hallucination"),
    ]
    cols = st.columns(3)
    for col, (label, _) in zip(cols, highlight):
        row = by_name.get(label)
        with col:
            if row:
                delta = "On target" if row.get("met") is True else (
                    "Below target" if row.get("met") is False else "Pilot metric"
                )
                col.metric(label, row.get("observed", "—"), delta=delta)
            else:
                col.metric(label, "—")

    rows = kpis.get("kpis") or []
    if rows:
        with st.expander("Full KPI table", expanded=False):
            st.dataframe(
                [
                    {
                        "KPI": r["kpi"],
                        "Target": r["target"],
                        "Observed": r["observed"],
                        "On target": (
                            "Yes"
                            if r.get("met") is True
                            else ("No" if r.get("met") is False else "Pilot")
                        ),
                    }
                    for r in rows
                ],
                use_container_width=True,
                hide_index=True,
            )

    if kpis.get("label_alignment_score") is not None:
        st.info(
            f"Correctness proxy (labelled data): alignment "
            f"{kpis['label_alignment_score']:.0%}. "
            f"{kpis.get('label_alignment_note', '')}"
        )


def _render_outcome(out: dict) -> None:
    section_title("Trust & quality assessment")
    expl = out.get("outcome_explanation") or {}
    findings = out.get("giskard_findings") or []
    headline = display_text(expl.get("headline", ""))
    summary = display_text(expl.get("summary", ""))
    reasons = [display_text(r) for r in expl.get("reasons", [])]

    passed = expl.get("outcome") == "pass" or out.get("outcome") == "pass"
    if passed:
        st.success(headline or "Low risk — trust & quality assessment passed")
        if summary:
            st.markdown(summary)
        for r in reasons:
            st.markdown(r)
    else:
        st.error(headline or "Elevated risk — review before acting")
        if summary:
            st.markdown(summary)
        for r in reasons:
            st.markdown(r)
        if findings:
            st.markdown("**Findings**")
            for i, f in enumerate(findings, 1):
                icon = "🔴" if f.get("level") == "critical" else "🟡"
                detail = display_text(f.get("detail", f.get("title", "")))
                st.markdown(f"{icon} **{i}.** {detail}")


def _render_giskard_trust(out: dict) -> None:
    live = out.get("giskard_live_scan") or {}
    if not live.get("enabled", True):
        st.caption("Giskard live scan is off (GISKARD_LIVE_SCAN=false).")
        return

    section_title("What Giskard did")
    st.markdown(display_text(GISKARD_ROLE))
    st.caption(
        f"Extra Groq calls for Giskard predict: {live.get('extra_groq_calls', 0)} "
        "(RCA already produced; scan assesses risk on that output only)."
    )
    for line in out.get("what_giskard_did") or []:
        st.markdown(f"- {display_text(line)}")

    scan = out.get("giskard_scan") or {}
    detectors = scan.get("detectors_run") or []
    if detectors:
        st.markdown("**Detectors run**")
        st.caption(", ".join(detectors))
    if scan.get("issue_count", 0) > 0:
        st.warning(
            f"Giskard reported {scan['issue_count']} issue(s) on this RCA output."
        )
    for issue in (scan.get("issues") or [])[:5]:
        title = display_text(issue.get("title", "Issue"))
        desc = display_text((issue.get("description") or "")[:300])
        st.markdown(f"- **{title}**: {desc}")

    html_path = out.get("giskard_native_html")
    if html_path and Path(html_path).is_file():
        with st.expander("Giskard scan report (this incident)", expanded=False):
            raw = Path(html_path).read_text(encoding="utf-8", errors="replace")
            components.html(raw, height=640, scrolling=True)
            st.download_button(
                "Download Giskard HTML",
                data=raw,
                file_name=Path(html_path).name,
                mime="text/html",
                use_container_width=True,
            )


def _render_grounding(out: dict) -> None:
    audit = out.get("grounding_audit") or {}
    if not audit:
        return
    section_title("Grounding & citations")
    st.markdown(
        "Where the AI RCA claims are supported by **your input** vs **ChromaDB**."
    )
    for src in audit.get("input_sources") or []:
        st.markdown(f"- {display_text(src)}")
    rc_ok = audit.get("root_cause_grounded")
    overlap = audit.get("root_cause_overlap", 0)
    if rc_ok:
        st.success(
            f"Probable root cause overlaps your signals (score {overlap:.0%})."
        )
    else:
        st.warning(
            f"Probable root cause has weak overlap with pasted signals (score {overlap:.0%}). "
            "Treat as hypothesis until verified."
        )
    rows = audit.get("evidence_citations") or []
    if rows:
        st.dataframe(
            [
                {
                    "Evidence claim": display_text(r.get("claim", "")),
                    "Grounded": r.get("grounded", ""),
                    "Source": display_text(r.get("source", "")),
                }
                for r in rows
            ],
            use_container_width=True,
            hide_index=True,
        )


def _render_recommendation(out: dict) -> None:
    section_title("Root cause analysis")
    c1, c2, c3, c4 = st.columns(4)
    badge = out.get("giskard_badge", "?")
    em = {"PASS": "🟢", "FLAG": "🟡", "FAIL": "🔴"}.get(badge, "⚪")
    latency = _fmt_latency(out.get("total_latency_ms", 0))
    trace = out.get("pipeline_trace") or {}

    c1.metric("Confidence", f"{out.get('confidence', 0)}%")
    with c2:
        c2.metric("Risk tier", f"{em} {badge}")
        c2.caption("Risk, not correctness")
    c3.metric("Draft time", latency)
    c4.metric("Similar incidents", trace.get("similar_count", 0))

    st.markdown("**Probable root cause**")
    root = html_lib.escape(display_text(out.get("probable_root_cause", "")))
    st.markdown(
        f'<div class="ofi-card"><p class="ofi-rca-root">{root}</p></div>',
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Supporting evidence**")
        for e in out.get("evidence") or []:
            st.markdown(f"- {display_text(e)}")
    with col_b:
        st.markdown("**Recommended actions**")
        for i, s in enumerate(out.get("next_steps") or [], 1):
            st.markdown(f"{i}. {display_text(s)}")

    if out.get("similar_incidents"):
        with st.expander("Related historical incidents"):
            for s in out["similar_incidents"]:
                st.markdown(
                    f"- **{s['incident_id']}** — {display_text(s['title'])} "
                    f"(similarity {s['similarity_score']:.0%})"
                )


def _render_results(out: dict) -> None:
    if out.get("error") and not out.get("probable_root_cause"):
        patch_red(
            "<h3>Could not process incident</h3>"
            f"<p>{html_lib.escape(display_text(out.get('error', '')))}</p>"
            "<p>Check required fields and try again.</p>"
        )
        return

    results_banner()
    if out.get("probable_root_cause"):
        _render_recommendation(out)
        _render_trust_kpis(out)
        _render_outcome(out)
        _render_giskard_trust(out)
        _render_grounding(out)


def _startup() -> None:
    if st.session_state.get("startup_done"):
        return
    log.info("ui.startup_begin")
    with st.spinner("Loading incident repository…"):
        st.session_state["startup"] = asyncio.run(run_startup_checks(settings))
    st.session_state["startup_done"] = True
    log.info("ui.startup_complete", **st.session_state["startup"].get("memory", {}))


def _render_sidebar() -> None:
    st.markdown("### ORI")
    st.caption("Operational Reasoning Intelligence")

    st.markdown(
        '<div class="ofi-sidebar-info">'
        "<p><strong>ORI</strong> = AI-assisted incident analysis: "
        "paste signals, get a draft root cause, trust assessment, and actions.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    _startup()
    mem = (st.session_state.get("startup") or {}).get("memory", {})
    count = int(mem.get("count", 0) or 0)

    st.metric(
        "Incident repository",
        count,
        help="Number of historical incidents stored in ChromaDB for similarity search.",
    )

    if count == 0:
        st.warning(
            "Repository is empty. Run: `python main.py --mode seed` "
            "(after `python datasets/download.py`)."
        )
    else:
        source = mem.get("source", "unknown")
        if source == "existing":
            loaded = "Already loaded from your local ChromaDB folder."
        elif source == "processed":
            loaded = (
                f"Auto-loaded {mem.get('seeded', count)} incidents from "
                "data/processed/ on this session."
            )
        elif source == "synthetic":
            loaded = "Auto-loaded from synthetic incident pool."
        else:
            loaded = "Historical incidents available for retrieval."

        st.markdown(
            f'<div class="ofi-sidebar-info">'
            f"<p><strong>What {count} means</strong></p>"
            f"<p>Past outages and alerts are embedded in <strong>ChromaDB</strong> "
            f"(collection <code>{mem.get('collection', 'ori_incidents')}</code>). "
            f"They are <em>not</em> the incident you type in the form.</p>"
            f"<p>When you click <strong>Analyze incident</strong>, ORI retrieves the "
            f"<strong>top 3</strong> closest matches and uses them for context, "
            f"grounding, and compare-with-historical-ID style actions.</p>"
            f"<p>{loaded}</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Severity labels (P1-P4)", expanded=False):
        st.markdown(
            """
**P1 - Critical**  
Complete outage or severe revenue / safety impact. *Example:* payment or revenue dashboard down for all users; error rate >50%.

**P2 - High**  
Major degradation; workaround may exist. *Example:* checkout 5x slower, elevated errors, but some traffic succeeds.

**P3 - Medium**  
Limited impact; core services healthy. *Example:* stale catalog cache affecting some product pages only.

**P4 - Low / informational**  
Planned work or negligible customer impact. *Example:* scheduled cert rotation on an internal admin tool.

---
Demo inputs: `testcases/` (markdown files testcase_01 … testcase_04).
            """
        )


with st.sidebar:
    _render_sidebar()

ofi_header(
    "Operational Reasoning Intelligence",
    "Signals → AI Reasoning → Trust & Quality Assessment → RCA Recommendation",
)

st.markdown(
    '<div class="ofi-input-panel">'
    "<h3>New incident</h3>"
    "<p style='color:#555;margin-top:0;'>"
    "Provide incident details and operational signals (logs, alerts, tickets). "
    "Required: title, severity, affected system, and either a description "
    "or at least one signal line."
    "</p></div>",
    unsafe_allow_html=True,
)

c1, c2 = st.columns(2)
with c1:
    title = st.text_input("Title", placeholder="Revenue Dashboard Unavailable - P1")
    severity = st.selectbox("Severity", ["P1", "P2", "P3", "P4"])
    affected_system = st.text_input("Affected system", placeholder="revenue-dashboard")
with c2:
    description = st.text_area(
        "Description",
        placeholder="What happened, when, and business impact…",
        height=100,
    )
    deployment_notes = st.text_area(
        "Deployment notes (optional)",
        placeholder="e.g. service v2.8.4 deployed 14:28 UTC",
        height=72,
    )

signals_text = st.text_area(
    "Signals (one per line)",
    placeholder=(
        "ERROR api-gateway: timeout to revenue-service\n"
        "ERROR revenue-service: pool exhausted\n"
        "ALERT monitoring: error rate 94%"
    ),
    height=120,
)

if st.button("Analyze incident", type="primary", use_container_width=True):
    raw = {
        "title": title,
        "description": description,
        "severity": severity,
        "affected_system": affected_system,
        "signals": [s.strip() for s in signals_text.splitlines() if s.strip()],
        "deployment_notes": deployment_notes or None,
        "source_dataset": "streamlit",
    }
    log.info("ui.run_clicked", title=(title or "")[:80], signals=len(raw["signals"]))
    with st.status("Analyzing incident…", expanded=True) as status:
        status.write("1/3 — Checking input and retrieving similar incidents…")
        status.write("2/3 — Generating RCA with Groq (1 API call)…")
        status.write("3/3 — Trust & quality assessment (rules + Giskard risk scan)…")
        out = asyncio.run(run_enterprise_rca(raw, settings, source_dataset="streamlit"))
        status.update(label="Analysis complete", state="complete")
    if out.get("probable_root_cause") and not out.get("giskard_findings"):
        out["giskard_findings"] = collect_findings(
            giskard_scan=out.get("giskard_scan"),
            giskard_suite=out.get("giskard_suite"),
            report_validation=out.get("giskard_report_validation"),
            validation_issues=out.get("validation_issues"),
        )
    st.session_state["last_result"] = out
    st.rerun()

if st.session_state.get("last_result"):
    st.markdown("---")
    _render_results(st.session_state["last_result"])
