"""Stratified sampling for governance evaluation (caps LLM spend)."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from layers.ingestion.schema import UnifiedIncident

_DB_KEYWORDS = ("database", "db", "postgres", "mysql", "pool", "connection", "sql")
_NET_KEYWORDS = ("network", "api", "gateway", "timeout", "redis", "cache", "http")


def _has_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(k in lower for k in keywords)


def _incident_text(inc: UnifiedIncident) -> str:
    parts = [inc.title, inc.description, inc.affected_system, *(inc.signals or [])]
    if inc.deployment_notes:
        parts.append(inc.deployment_notes)
    return " ".join(parts)


def _bucket(inc: UnifiedIncident) -> str:
    text = _incident_text(inc)
    has_deploy = bool(inc.deployment_notes and inc.deployment_notes.strip())
    if inc.severity == "P1" and has_deploy:
        return "p1_deploy"
    if inc.severity == "P1":
        return "p1_no_deploy"
    if inc.severity == "P2":
        return "p2"
    if _has_keyword(text, _DB_KEYWORDS):
        return "db_theme"
    if _has_keyword(text, _NET_KEYWORDS):
        return "net_theme"
    return "other"


def select_eval_sample(
    incidents: list[UnifiedIncident],
    n: int = 5,
    seed: int = 42,
) -> list[UnifiedIncident]:
    """
    Pick up to n incidents with diverse buckets (P1+deploy, P1, P2, DB, network).
    Falls back to random fill if buckets are sparse.
    """
    if not incidents:
        return []
    if len(incidents) <= n:
        return list(incidents)

    priority = ("p1_deploy", "p1_no_deploy", "p2", "db_theme", "net_theme", "other")
    by_bucket: dict[str, list[UnifiedIncident]] = {b: [] for b in priority}
    for inc in incidents:
        by_bucket[_bucket(inc)].append(inc)

    rng = random.Random(seed)
    chosen: list[UnifiedIncident] = []
    seen_ids: set[str] = set()

    for bucket in priority:
        if len(chosen) >= n:
            break
        pool = [i for i in by_bucket[bucket] if i.incident_id not in seen_ids]
        if not pool:
            continue
        pick = rng.choice(pool)
        chosen.append(pick)
        seen_ids.add(pick.incident_id)

    remaining = [i for i in incidents if i.incident_id not in seen_ids]
    rng.shuffle(remaining)
    for inc in remaining:
        if len(chosen) >= n:
            break
        chosen.append(inc)
        seen_ids.add(inc.incident_id)

    return chosen[:n]
