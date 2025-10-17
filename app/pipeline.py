"""Core pipeline helpers for scraping and composing earnings data."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict

from .cache import (
    cache_path,
    is_cache_fresh,
    load_cache,
    load_latest_enrichment,
    write_cache,
)
from .scraper import YahooEarningsScraper
from .utils import DateWindow, clamp_days, now_sgt, parse_number

LOGGER = logging.getLogger("app.pipeline")
DEFAULT_DAYS = 7
MAX_DAYS = 14


def augment_rows(days: list[dict[str, Any]], ticker_map: Dict[str, Any]) -> None:
    for day in days:
        for row in day.get("rows", []):
            symbol = (row.get("symbol") or row.get("ticker") or "").strip().upper()
            info = ticker_map.get(symbol) if symbol else None
            if info:
                row["stockPrice"] = info.get("price")
                if row.get("epsEstimate") is None:
                    row["epsEstimate"] = info.get("eps_estimate_curr_q")
                if row.get("revenueEstimate") is None:
                    row["revenueEstimate"] = info.get("revenue_estimate_curr_q")
            row.setdefault("epsEstimate", parse_number(row.get("eps_estimate")))
            row.setdefault("revenueEstimate", parse_number(row.get("revenue_estimate")))
            row.setdefault("stockPrice", parse_number(row.get("stock_price")))


async def build_payload(start: date, days: int, scraper: YahooEarningsScraper | None = None) -> Dict[str, Any]:
    window = DateWindow.from_start_and_days(start, days)
    cache_file = cache_path(window.start.isoformat(), window.end.isoformat())
    enrichment = load_latest_enrichment() or {}
    ticker_map = enrichment.get("tickers", {})

    cached = load_cache(cache_file)
    if cached and is_cache_fresh(cache_file):
        augment_rows(cached.get("days", []), ticker_map)
        cached["updated_at"] = now_sgt().isoformat()
        write_cache(cache_file, cached)
        return cached

    fallback = cached
    scraper = scraper or YahooEarningsScraper()

    try:
        LOGGER.info("Cache miss for %s → %s. Scraping...", window.start, window.end)
        data = await scraper.fetch_window(window.start, days)
        augment_rows(data, ticker_map)
        payload: Dict[str, Any] = {
            "params": window.as_params(),
            "updated_at": now_sgt().isoformat(),
            "source": "Yahoo Finance earnings calendar",
            "days": data,
        }
        write_cache(cache_file, payload)
        return payload
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Scrape failed, using cached data if available: %s", exc)
        if fallback:
            augment_rows(fallback.get("days", []), ticker_map)
            fallback["updated_at"] = now_sgt().isoformat()
            return fallback
        raise
