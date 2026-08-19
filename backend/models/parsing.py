"""Shared parsing helpers for messy source data.

Real exports (and our synthetic ones, on purpose — see backend/synth) mix
date formats and use "yes"/"no" style booleans. Adapters and schemas both
need the same tolerant parsing, so it lives here rather than duplicated.
"""

from __future__ import annotations

from datetime import datetime

DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S %z",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%B %d, %Y",
    "%Y-%m-%d",
]


def parse_flexible_date(raw: str) -> datetime:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("empty date")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"unparseable date: {raw!r}")


TRUE_STRINGS = {"yes", "true", "1", "y"}
FALSE_STRINGS = {"no", "false", "0", "n", ""}


def parse_flexible_bool(raw: str | None) -> bool:
    if raw is None:
        return False
    normalized = raw.strip().lower()
    if normalized in TRUE_STRINGS:
        return True
    if normalized in FALSE_STRINGS:
        return False
    raise ValueError(f"unparseable boolean: {raw!r}")
