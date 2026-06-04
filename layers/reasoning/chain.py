"""Groq single-call RCA: correlate signals and return structured JSON."""
import json
import time

import structlog
from groq import AsyncGroq

from config.settings import Settings
from layers.ingestion.schema import SimilarIncident, UnifiedIncident
from layers.ingestion.text_utils import normalize_unicode_text
from layers.reasoning import prompts
from layers.reasoning.rca_output import RCAOutput

logger = structlog.get_logger(__name__)


def _format_signals(signals: list[str]) -> str:
    if not signals:
        return "(no signals provided)"
    return "\n".join(f"  • {normalize_unicode_text(s)}" for s in signals)


def _format_similar(similar: list[SimilarIncident]) -> str:
    if not similar:
        return "(no similar incidents found in history)"
    parts = []
    for s in similar:
        rc = normalize_unicode_text(s.root_cause or "unknown")
        title = normalize_unicode_text(s.title)
        desc = normalize_unicode_text(s.description[:200])
        parts.append(
            f"[{s.incident_id}] {title} (score={s.similarity_score:.2f})\n"
            f"  Root cause: {rc}\n"
            f"  Description: {desc}"
        )
    return "\n\n".join(parts)


class RCAChain:
    """One Groq call: correlation + RCA JSON (official Groq SDK)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = AsyncGroq(api_key=settings.groq_api_key)

    async def _complete(self, messages: list[dict[str, str]]) -> str:
        response = await self._client.chat.completions.create(
            model=self.settings.groq_model,
            messages=messages,
            max_tokens=self.settings.groq_max_tokens,
            temperature=0.1,
        )
        return (response.choices[0].message.content or "").strip()

    async def run(
        self,
        incident: UnifiedIncident,
        similar_incidents: list[SimilarIncident],
    ) -> RCAOutput:
        t_start = time.monotonic()
        logger.info(
            "layer.start",
            layer="reasoning",
            incident_id=incident.incident_id,
            similar_count=len(similar_incidents),
            groq_calls=1,
        )

        user_prompt = prompts.UNIFIED_RCA_PROMPT.format(
            title=normalize_unicode_text(incident.title),
            severity=incident.severity,
            affected_system=normalize_unicode_text(incident.affected_system),
            description=normalize_unicode_text(incident.description),
            signals=_format_signals(incident.signals),
            deployment_notes=normalize_unicode_text(incident.deployment_notes or "(none)"),
            similar_incidents=_format_similar(similar_incidents),
        )
        logger.debug("prompt.sent", step="unified_rca", prompt_preview=user_prompt[:300])

        rca_raw = await self._complete(
            [
                {"role": "system", "content": prompts.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
        )
        rca_ms = int((time.monotonic() - t_start) * 1000)

        rca_output = self._parse_rca(rca_raw)
        rca_output.model_used = self.settings.groq_model
        rca_output.latency_ms = rca_ms

        logger.info(
            "groq.rca_generated",
            confidence=rca_output.confidence,
            model=rca_output.model_used,
            latency_ms=rca_output.latency_ms,
            groq_calls=1,
        )
        return rca_output

    def _parse_rca(self, raw: str) -> RCAOutput:
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        try:
            data = json.loads(raw)
            trace = normalize_unicode_text(
                data.get("correlation_summary") or data.get("reasoning_trace") or ""
            )
            return RCAOutput(
                probable_root_cause=normalize_unicode_text(
                    data.get("probable_root_cause", "Unable to determine root cause")
                ),
                confidence=int(data.get("confidence", 0)),
                affected_components=[
                    normalize_unicode_text(c) for c in data.get("affected_components", [])
                ],
                evidence=[normalize_unicode_text(e) for e in data.get("evidence", [])],
                next_steps=[normalize_unicode_text(s) for s in data.get("next_steps", [])],
                similar_incident_ids=data.get("similar_incident_ids", []),
                reasoning_trace=trace,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("reasoning.parse_failed", error=str(e), raw_preview=raw[:200])
            return RCAOutput(
                probable_root_cause=f"Parse error - raw response: {normalize_unicode_text(raw[:300])}",
                confidence=0,
                reasoning_trace="",
            )
