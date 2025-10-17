"""
Cache helpers for storing and retrieving scraped earnings data.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from .utils import now_sgt

CACHE_DIR = Path("./cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHE_MAX_AGE = timedelta(hours=24)
ENRICH_PREFIX = "yahoo_enriched_"


def cache_path(start: str, end: str) -> Path:
    """Return cache path for given ISO start/end dates."""
    safe_start = start.replace("-", "")
    safe_end = end.replace("-", "")
    filename = f"yahoo_earnings_{safe_start}_{safe_end}.json"
    return CACHE_DIR / filename


def is_cache_fresh(path: Path, max_age: timedelta = CACHE_MAX_AGE) -> bool:
    """Return True if cache file exists and is younger than max_age."""
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=now_sgt().tzinfo)
    fresh = now_sgt() - mtime < max_age
    return fresh


def load_cache(path: Path) -> dict[str, Any] | None:
    """Load JSON cache from disk if it exists."""
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def write_cache(path: Path, payload: Mapping[str, Any]) -> None:
    """Persist payload to disk as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)


def latest_enrichment_path() -> Path | None:
    files = sorted(CACHE_DIR.glob(f"{ENRICH_PREFIX}*.json"), reverse=True)
    return files[0] if files else None


def load_latest_enrichment() -> dict[str, Any] | None:
    path = latest_enrichment_path()
    if not path or not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def enrichment_cache_path_for(day: date) -> Path:
    return CACHE_DIR / f"{ENRICH_PREFIX}{day.isoformat()}.json"
