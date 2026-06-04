"""Generate synthetic labeled incidents via Groq for Giskard test suite."""
import asyncio
import json
import os
from pathlib import Path

import structlog
from groq import AsyncGroq

from layers.ingestion.schema import UnifiedIncident
from layers.ingestion.normaliser import normalise

logger = structlog.get_logger(__name__)

_SYSTEM = """You are an expert SRE generating realistic synthetic incident data for AI testing.
Always respond with valid JSON only — no markdown, no explanation."""

_USER_TEMPLATE = """Generate {n} realistic enterprise IT incidents as a JSON array.
Each element must have EXACTLY these fields:
{{
  "incident_id": "SYN-<3-digit-number>",
  "title": "<short descriptive title>",
  "description": "<2-3 sentence description of what's happening>",
  "severity": "<P1|P2|P3|P4>",
  "affected_system": "<service or component name>",
  "signals": ["<log line 1>", "<log line 2>", "<log line 3>"],
  "deployment_notes": "<recent deployment or null>",
  "source_dataset": "synthetic",
  "true_root_cause": "<the actual root cause — be specific>"
}}
Mix severities. Include database, network, memory, deployment, and dependency failure causes.
Batch {batch_start} to {batch_end}. Return ONLY the JSON array."""


async def generate_synthetic_incidents(
    n: int = 50,
    output_path: str = "./data/synthetic/synthetic_incidents.json",
    model: str = "llama-3.3-70b-versatile",
    api_key: str | None = None,
) -> list[UnifiedIncident]:
    """Use Groq to generate n synthetic labeled incidents and save to disk."""
    client = AsyncGroq(api_key=api_key or os.environ.get("GROQ_API_KEY", ""))
    batch_size = 10
    all_incidents: list[UnifiedIncident] = []

    for batch_start in range(1, n + 1, batch_size):
        batch_end = min(batch_start + batch_size - 1, n)
        prompt = _USER_TEMPLATE.format(
            n=batch_end - batch_start + 1,
            batch_start=batch_start,
            batch_end=batch_end,
        )
        logger.info("synthetic.generating_batch", batch_start=batch_start, batch_end=batch_end)
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=4096,
                temperature=0.8,
            )
            raw_json = response.choices[0].message.content or "[]"
            # Strip any accidental markdown fences
            raw_json = raw_json.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            records: list[dict] = json.loads(raw_json)
            batch_incidents = [
                inc for r in records if (inc := normalise(r, "synthetic")) is not None
            ]
            all_incidents.extend(batch_incidents)
            logger.info("synthetic.batch_done", count=len(batch_incidents))
        except Exception as e:
            logger.error("synthetic.batch_failed", batch_start=batch_start, error=str(e), exc_info=True)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump([inc.model_dump(mode="json") for inc in all_incidents], f, indent=2, default=str)

    logger.info("synthetic.saved", path=output_path, total=len(all_incidents))
    return all_incidents


if __name__ == "__main__":
    asyncio.run(generate_synthetic_incidents())
