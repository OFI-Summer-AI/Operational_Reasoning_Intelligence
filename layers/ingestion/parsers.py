"""One parser per source type. Each returns list[dict] of raw fields."""
import json
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


def parse_csv(path: str | Path) -> list[dict[str, Any]]:
    """Parse CSV file → list of row dicts."""
    path = Path(path)
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
        records = df.to_dict(orient="records")
        logger.info("parser.csv.done", path=str(path), rows=len(records))
        return records
    except Exception as e:
        logger.error("parser.csv.failed", path=str(path), error=str(e), exc_info=True)
        return []


def parse_json(path: str | Path) -> list[dict[str, Any]]:
    """Parse JSON file (object or array) → list of dicts."""
    path = Path(path)
    try:
        with open(path) as f:
            data = json.load(f)
        records = data if isinstance(data, list) else [data]
        logger.info("parser.json.done", path=str(path), rows=len(records))
        return records
    except Exception as e:
        logger.error("parser.json.failed", path=str(path), error=str(e), exc_info=True)
        return []


def parse_pdf(path: str | Path) -> list[dict[str, Any]]:
    """Parse PDF → one record per page with extracted text."""
    path = Path(path)
    try:
        import pdfplumber

        records = []
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if text.strip():
                    records.append(
                        {
                            "page": i + 1,
                            "raw_text": text,
                            "title": f"{path.stem} — page {i + 1}",
                            "description": text[:500],
                        }
                    )
        logger.info("parser.pdf.done", path=str(path), pages=len(records))
        return records
    except Exception as e:
        logger.error("parser.pdf.failed", path=str(path), error=str(e), exc_info=True)
        return []


def parse_markdown(path: str | Path) -> list[dict[str, Any]]:
    """Parse markdown postmortem file → incident dict."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        sections: dict[str, str] = {}
        current: str | None = None
        buf: list[str] = []

        for line in text.splitlines():
            if line.startswith("#"):
                if current is not None:
                    sections[current] = "\n".join(buf).strip()
                current = line.lstrip("#").strip().lower()
                buf = []
            else:
                buf.append(line)
        if current:
            sections[current] = "\n".join(buf).strip()

        root_cause = (
            sections.get("root cause")
            or sections.get("root_cause")
            or sections.get("cause")
            or ""
        )
        description = (
            sections.get("summary")
            or sections.get("description")
            or sections.get("overview")
            or text[:500]
        )
        record = {
            "title": path.stem.replace("-", " ").replace("_", " ").title(),
            "description": description,
            "raw_text": text,
            "true_root_cause": root_cause,
            "source_dataset": "danluu_postmortems",
        }
        logger.debug("parser.markdown.done", file=path.name)
        return [record]
    except Exception as e:
        logger.error("parser.markdown.failed", path=str(path), error=str(e), exc_info=True)
        return []


def parse_log_lines(path: str | Path, max_lines: int = 200) -> list[dict[str, Any]]:
    """Parse HDFS-style log file → one record with signals as individual log lines."""
    path = Path(path)
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        # Keep only lines that look like errors/warnings
        interesting = [
            ln for ln in lines if any(kw in ln.upper() for kw in ("ERROR", "WARN", "FATAL", "CRITICAL"))
        ][:max_lines]
        record = {
            "title": f"Log signals from {path.name}",
            "description": f"Extracted {len(interesting)} error/warning lines from {path.name}",
            "signals": interesting,
            "raw_text": "\n".join(interesting),
            "source_dataset": "hdfs_logs",
        }
        logger.info("parser.logs.done", path=str(path), signals=len(interesting))
        return [record]
    except Exception as e:
        logger.error("parser.logs.failed", path=str(path), error=str(e), exc_info=True)
        return []
