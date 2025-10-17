"""Yahoo Finance enrichment job using yfinance."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterable, Optional, Set

import pandas as pd
import yfinance as yf

from .cache import CACHE_DIR, enrichment_cache_path_for, latest_enrichment_path
from .utils import now_sgt, parse_number

LOGGER = logging.getLogger("app.enrich")
logging.basicConfig(level=logging.INFO)

ENRICH_MAX_AGE = timedelta(hours=24)


def load_cached_tickers() -> Set[str]:
    tickers: Set[str] = set()
    for file in CACHE_DIR.glob("yahoo_earnings_*.json"):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for day in data.get("days", []):
            for row in day.get("rows", []):
                symbol = row.get("symbol")
                if symbol:
                    tickers.add(symbol.strip().upper())
    return tickers


@dataclass
class TickerResult:
    symbol: str
    price: Optional[float]
    eps_estimate: Optional[float]
    revenue_estimate: Optional[float]

    def as_dict(self) -> Dict[str, Optional[float]]:
        return {
            "price": self.price,
            "eps_estimate_curr_q": self.eps_estimate,
            "revenue_estimate_curr_q": self.revenue_estimate,
        }


def _extract_current_column(df: pd.DataFrame) -> Optional[str]:
    for column in df.columns:
        if "current" in column.lower():
            return column
    return df.columns[0] if len(df.columns) else None


def _fetch_eps_revenue(analysis: Optional[pd.DataFrame]) -> tuple[Optional[float], Optional[float]]:
    if analysis is None or analysis.empty:
        return None, None
    column = _extract_current_column(analysis)
    if not column:
        return None, None
    eps = None
    revenue = None
    if "eps estimate" in analysis.index:
        eps = parse_number(str(analysis.loc["EPS Estimate", column]))
    if "revenue estimate" in analysis.index:
        revenue = parse_number(str(analysis.loc["Revenue Estimate", column]))
    return eps, revenue


def _fetch_ticker(symbol: str) -> TickerResult:
    ticker = yf.Ticker(symbol)
    price = None
    eps = None
    revenue = None
    try:
        fast_info = getattr(ticker, "fast_info", {})
        price = fast_info.get("lastPrice")
        if price is None:
            info = ticker.info or {}
            price = info.get("regularMarketPrice")
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.debug("Failed to fetch price for %s: %s", symbol, exc)

    try:
        analysis = ticker.get_analysis()
    except Exception:  # pylint: disable=broad-except
        analysis = None
    eps, revenue = _fetch_eps_revenue(analysis)

    if revenue is None:
        try:
            forecasts = ticker.get_earnings_forecast()
            if forecasts is not None and not forecasts.empty:
                column = _extract_current_column(forecasts)
                if column and "revenueForecast" in forecasts.index:
                    revenue = parse_number(str(forecasts.loc["revenueForecast", column]))
        except Exception:  # pylint: disable=broad-except
            pass

    return TickerResult(symbol, price, eps, revenue)


async def enrich_tickers(tickers: Iterable[str], max_concurrency: int = 3, force: bool = False) -> Dict[str, Dict[str, Optional[float]]]:
    tickers = sorted(set(tickers))
    if not tickers:
        raise ValueError("No tickers found in earnings cache.")

    output_path = enrichment_cache_path_for(now_sgt().date())
    if not force:
        latest = latest_enrichment_path()
        if latest and now_sgt() - datetime.fromtimestamp(latest.stat().st_mtime, tz=now_sgt().tzinfo) < ENRICH_MAX_AGE:
            LOGGER.info("Latest enrichment cache is fresh: %s", latest.name)
            return json.loads(latest.read_text(encoding="utf-8"))

    results: Dict[str, Dict[str, Optional[float]]] = {}
    semaphore = asyncio.Semaphore(max_concurrency)
    total = len(tickers)

    async def process(symbol: str, position: int) -> None:
        async with semaphore:
            await asyncio.sleep(random.uniform(0.3, 0.6))
            res = await asyncio.to_thread(_fetch_ticker, symbol)
            results[symbol] = res.as_dict()
            LOGGER.info("Enriched %s/%s ticker %s", position, total, symbol)

    await asyncio.gather(*(process(symbol, idx + 1) for idx, symbol in enumerate(tickers)))

    payload = {
        "updated_at": now_sgt().isoformat(),
        "source": "Yahoo Finance",
        "tickers": results,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    LOGGER.info("Enrichment written to %s (%s tickers)", output_path, len(results))
    return payload


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Yahoo earnings enrichment job")
    parser.add_argument("--force", action="store_true", help="Force refresh even if cache is fresh")
    parser.add_argument("--max-concurrency", type=int, default=3, help="Maximum concurrent ticker lookups")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    tickers = load_cached_tickers()
    if not tickers:
        LOGGER.warning("No tickers discovered from earnings cache. Nothing to do.")
        return

    LOGGER.info("Starting enrichment for %s tickers", len(tickers))
    asyncio.run(enrich_tickers(tickers, max_concurrency=args.max_concurrency, force=args.force))


if __name__ == "__main__":  # pragma: no cover
    main()
