"""Command-line helper to refresh Yahoo earnings cache."""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, timedelta

from .enrich import enrich_tickers, load_cached_tickers
from .pipeline import DEFAULT_DAYS, build_payload, clamp_days
from .scraper import YahooEarningsScraper
from .utils import parse_start_date

LOGGER = logging.getLogger("app.refresh")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh Yahoo earnings cache")
    parser.add_argument("--start", help="Start date YYYY-MM-DD (default: today SGT)")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="Window length (1-14 days)")
    parser.add_argument("--enrich", action="store_true", help="Also refresh ticker enrichment cache")
    parser.add_argument("--max-concurrency", type=int, default=3, help="Max concurrent Playwright tasks for enrichment")
    return parser.parse_args()


def clamp_window(start: str | None, days: int) -> tuple[date, int]:
    start_date = parse_start_date(start)
    window_days = clamp_days(days)
    return start_date, window_days


def summarize(payload: dict) -> str:
    totals = [day.get("count", 0) for day in payload.get("days", [])]
    return f"{sum(totals)} rows across {len(totals)} day(s)"


async def run_refresh(start: date, days: int, do_enrich: bool, max_concurrency: int) -> None:
    scraper = YahooEarningsScraper()
    payload = await build_payload(start, days, scraper)
    LOGGER.info("Earnings cache updated: %s", summarize(payload))

    if do_enrich:
        tickers = load_cached_tickers()
        if not tickers:
            LOGGER.warning("No tickers found to enrich.")
        else:
            await enrich_tickers(tickers, max_concurrency=max_concurrency, force=True)


def main() -> None:
    args = parse_args()
    start_date, window_days = clamp_window(args.start, args.days)
    end_date = start_date + timedelta(days=window_days - 1)
    LOGGER.info("Refreshing earnings window %s → %s (days=%s)", start_date, end_date, window_days)
    try:
        asyncio.run(run_refresh(start_date, window_days, args.enrich, args.max_concurrency))
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Refresh failed: %s", exc)
        raise


if __name__ == "__main__":  # pragma: no cover
    main()
