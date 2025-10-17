"""
Utility helpers for date handling, user-agent rotation, and miscellaneous helpers.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional, Sequence
from zoneinfo import ZoneInfo

SINGAPORE_TZ = ZoneInfo("Asia/Singapore")

USER_AGENTS: Sequence[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0",
)


def now_sgt() -> datetime:
    """Return the current time in Singapore timezone."""
    return datetime.now(tz=SINGAPORE_TZ)


def default_start_date() -> date:
    """Return today's date in Singapore."""
    return now_sgt().date()


def parse_start_date(start: str | None) -> date:
    """Parse YYYY-MM-DD date or use today's date in Singapore timezone."""
    if not start:
        return default_start_date()
    try:
        parsed = datetime.strptime(start, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Invalid start date format. Expected YYYY-MM-DD.") from exc
    return parsed


def clamp_days(days: int, min_days: int = 1, max_days: int = 14) -> int:
    """Clamp day window to a safe range."""
    return max(min_days, min(max_days, days))


def date_sequence(start: date, days: int) -> List[date]:
    """Return a list of sequential dates starting from start inclusive."""
    return [start + timedelta(days=offset) for offset in range(days)]


def choose_user_agent(seed: int | None = None) -> str:
    """
    Choose a user-agent string. If seed provided, deterministic selection.
    """
    if seed is not None:
        rng = random.Random(seed)
        return rng.choice(USER_AGENTS)
    return random.choice(USER_AGENTS)


@dataclass(slots=True, frozen=True)
class DateWindow:
    """Convenience container for a start/end window expressed as date objects."""

    start: date
    end: date

    @classmethod
    def from_start_and_days(cls, start: date, days: int) -> "DateWindow":
        end = start + timedelta(days=days - 1)
        return cls(start=start, end=end)

    def as_params(self) -> dict[str, str]:
        return {
            "start_day": self.start.isoformat(),
            "end_day": self.end.isoformat(),
        }


def parse_number(value: float | int | str | None) -> Optional[float]:
    """Parse numeric string or numeric value with optional K/M/B/T suffix to float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value == value else None  # handle NaN
    cleaned = str(value).strip().replace(",", "")
    if not cleaned:
        return None
    multipliers = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}
    suffix = cleaned[-1].upper()
    multiplier = multipliers.get(suffix)
    if multiplier:
        try:
            return float(cleaned[:-1]) * multiplier
        except ValueError:
            return None
    try:
        return float(cleaned)
    except ValueError:
        return None
