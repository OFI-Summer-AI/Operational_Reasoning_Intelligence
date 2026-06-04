"""Normalize text for storage and UI (unicode dashes, mojibake)."""
from __future__ import annotations

import re


def normalize_unicode_text(text: str | None) -> str:
    """
    Clean incident text for display and ChromaDB metadata.
    - Repairs common UTF-8-as-Latin-1 mojibake (e.g. â€" from em dash)
    - Replaces unicode dashes with ASCII " - "
    """
    if not text:
        return ""
    s = str(text)
    if "â" in s or "Ã" in s:
        try:
            repaired = s.encode("latin-1").decode("utf-8")
            if repaired:
                s = repaired
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
    s = (
        s.replace("\u2014", " - ")
        .replace("\u2013", " - ")
        .replace("\u2012", "-")
        .replace("\u00a0", " ")
    )
    return re.sub(r"\s+", " ", s).strip()
