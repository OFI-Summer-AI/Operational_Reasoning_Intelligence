"""Format RCAReport for different output targets."""
import json
from datetime import datetime

from layers.output.report import RCAReport

_BADGE_EMOJI = {"PASS": "✅", "FLAG": "⚠️", "FAIL": "❌"}
_CONF_EMOJI = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}


def to_json(report: RCAReport, indent: int = 2) -> str:
    """Serialize report to pretty JSON string."""
    return report.model_dump_json(indent=indent)


def to_dict(report: RCAReport) -> dict:
    """Serialize report to plain dict (datetime → ISO string)."""
    return json.loads(report.model_dump_json())


def to_terminal(report: RCAReport) -> str:
    """Human-readable terminal output."""
    badge_emoji = _BADGE_EMOJI.get(report.giskard_badge, "?")
    conf_emoji = _CONF_EMOJI.get(report.confidence_label, "")
    lines = [
        "",
        "═" * 60,
        f"  ORI Probable Root Cause Report",
        f"  Incident: {report.incident_id}",
        f"  Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "═" * 60,
        "",
        f"  Root Cause: {report.probable_root_cause}",
        f"  Confidence: {conf_emoji} {report.confidence}% ({report.confidence_label})",
        f"  Trust Badge: {badge_emoji} {report.giskard_badge}",
        "",
    ]
    if report.affected_components:
        lines.append("  Affected Components:")
        for c in report.affected_components:
            lines.append(f"    • {c}")
        lines.append("")

    if report.evidence:
        lines.append("  Evidence:")
        for e in report.evidence:
            lines.append(f"    • {e}")
        lines.append("")

    if report.next_steps:
        lines.append("  Next Steps:")
        for i, step in enumerate(report.next_steps, 1):
            lines.append(f"    {i}. {step}")
        lines.append("")

    if report.similar_incidents:
        lines.append("  Similar Historical Incidents:")
        for s in report.similar_incidents:
            lines.append(f"    • [{s.incident_id}] {s.title} (score={s.similarity_score:.2f})")
        lines.append("")

    if report.validation_issues:
        lines.append("  Trust assessment issues:")
        for issue in report.validation_issues:
            lines.append(f"    ⚠ {issue}")
        lines.append("")

    lines.append(f"  Model: {report.model_used}  |  Latency: {report.total_latency_ms}ms")
    lines.append("═" * 60)
    return "\n".join(lines)
