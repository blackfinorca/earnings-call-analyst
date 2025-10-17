"""Yahoo Finance enrichment job using RapidAPI quotes endpoint."""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, Optional, Set, Tuple

import requests

from .cache import CACHE_DIR, enrichment_cache_path_for, latest_enrichment_path
from .utils import now_sgt, parse_number

LOGGER = logging.getLogger("app.enrich")
logging.basicConfig(level=logging.INFO)

API_HOST = "yahoo-finance15.p.rapidapi.com"
QUOTES_URL = f"https://{API_HOST}/api/v1/markets/stock/quotes"
DEFAULT_API_KEY = "f3ba37d23bmsh7f5f08200423752p124129jsn859ceeb7bbd1"
DATA_CLIENT_PATH = Path("src/utils/dataClient.js")
DEFAULT_SLEEP_RANGE: Tuple[float, float] = (0.3, 0.6)
ENRICH_MAX_AGE = timedelta(hours=24)


def detect_frontend_json_path() -> Path:
    if DATA_CLIENT_PATH.exists():
        for line in DATA_CLIENT_PATH.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("import earningsData") and "../data/" in stripped:
                start = stripped.find("../data/") + len("../data/")
                end = stripped.find("\"", start)
                if end != -1:
                    return Path("src/data") / stripped[start:end]
                break
    return Path("src/data/earnings_data.json")


FRONTEND_JSON = detect_frontend_json_path()


def load_cached_tickers() -> Set[str]:
    tickers: Set[str] = set()
    paths = []
    if FRONTEND_JSON.exists():
        paths.append(FRONTEND_JSON)
    paths.extend(sorted(CACHE_DIR.glob("yahoo_earnings_*.json")))

    for file in paths:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for day in data.get("days", []):
            for row in day.get("rows", []):
                symbol = row.get("symbol") or row.get("ticker")
                if symbol:
                    tickers.add(symbol.strip().upper())
    return tickers


def get_api_key(explicit: str | None = None) -> str:
    key = explicit or os.getenv("RAPIDAPI_KEY") or DEFAULT_API_KEY
    if not key:
        raise ValueError("RapidAPI key missing. Set RAPIDAPI_KEY or use --api-key.")
    return key


def flatten_items(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key, value
            yield from flatten_items(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from flatten_items(item)


def extract_metrics(entry: dict) -> Dict[str, Optional[float]]:
    price = None
    eps = None
    revenue = None
    volume = None
    market_cap = None
    pe_ratio = None
    year_high = None
    year_low = None
    price_keys = {"regularmarketprice", "marketprice", "lastprice", "price", "regularmarketpreviousclose"}
    eps_keys = {"epsestimate", "epsforward", "eps", "earningsestimate", "epsquarterly", "epssurprise"}
    revenue_keys = {"revenuestimate", "revenueforecast", "totalrevenue", "revenue"}
    volume_keys = {"volume", "regularmarketvolume", "totalvolume", "sharestraded"}
    market_cap_keys = {"marketcap", "marketcapitalization", "marketcapitalest", "marketcapital"}
    pe_keys = {"peratio", "trailingpe", "forwardpe", "pe"}
    high_keys = {"fiftytwo_weekhigh", "52weekhigh", "week52high", "fiftytwo_weekhi"}
    low_keys = {"fiftytwo_weeklow", "52weeklow", "week52low", "fiftytwo_weeklo"}

    for key, value in flatten_items(entry):
        if not isinstance(key, str):
            continue
        normalized = key.lower()
        if price is None and normalized in price_keys:
            price = parse_number(value)
        elif price is None and "price" in normalized:
            price = parse_number(value)
        elif eps is None and normalized in eps_keys:
            eps = parse_number(value)
        elif eps is None and "eps" in normalized:
            eps = parse_number(value)
        elif revenue is None and normalized in revenue_keys:
            revenue = parse_number(value)
        elif revenue is None and "revenue" in normalized:
            revenue = parse_number(value)
        elif volume is None and normalized in volume_keys:
            volume = parse_number(value)
        elif volume is None and "volume" in normalized:
            volume = parse_number(value)
        elif market_cap is None and normalized in market_cap_keys:
            market_cap = parse_number(value)
        elif market_cap is None and "marketcap" in normalized:
            market_cap = parse_number(value)
        elif pe_ratio is None and normalized in pe_keys:
            pe_ratio = parse_number(value)
        elif pe_ratio is None and "pe" in normalized and "peg" not in normalized:
            pe_ratio = parse_number(value)
        elif year_high is None and normalized in high_keys:
            year_high = parse_number(value)
        elif year_high is None and "52" in normalized and "high" in normalized:
            year_high = parse_number(value)
        elif year_low is None and normalized in low_keys:
            year_low = parse_number(value)
        elif year_low is None and "52" in normalized and "low" in normalized:
            year_low = parse_number(value)

    return {
        "price": price,
        "eps_estimate_curr_q": eps,
        "revenue_estimate_curr_q": revenue,
        "volume": volume,
        "market_cap": market_cap,
        "pe_ratio": pe_ratio,
        "year_high": year_high,
        "year_low": year_low,
    }


def select_entry(symbol: str, payload: dict) -> dict:
    candidates = []
    if isinstance(payload, dict):
        for key in ("data", "result", "quotes", "response", "items"):
            val = payload.get(key)
            if isinstance(val, list):
                candidates.extend(val)
            elif isinstance(val, dict):
                candidates.extend(val.values())
        if not candidates:
            candidates = [payload]
    elif isinstance(payload, list):
        candidates = payload

    upper = symbol.upper()
    for item in candidates:
        if isinstance(item, dict):
            entry_symbol = item.get("symbol") or item.get("ticker") or item.get("instrument")
            if entry_symbol and entry_symbol.upper() == upper:
                return item
    return candidates[0] if candidates and isinstance(candidates[0], dict) else {}


def fetch_quote(session: requests.Session, api_key: str, symbol: str) -> Dict[str, Optional[float]]:
    params = {"ticker": symbol}
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": API_HOST,
        "accept": "application/json",
    }
    try:
        response = session.get(QUOTES_URL, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Failed to fetch quote for %s: %s", symbol, exc)
        return {"price": None, "eps_estimate_curr_q": None, "revenue_estimate_curr_q": None}

    entry = select_entry(symbol, payload)
    metrics = extract_metrics(entry)
    LOGGER.debug("Metrics for %s: %s", symbol, metrics)
    return metrics


def update_frontend_json(ticker_map: Dict[str, Dict[str, Optional[float]]]) -> None:
    frontend_path = detect_frontend_json_path()
    if not frontend_path.exists():
        LOGGER.warning("Frontend JSON %s does not exist; skipping update.", frontend_path)
        return

    try:
        data = json.loads(frontend_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        LOGGER.error("Failed to read %s: %s", frontend_path, exc)
        return

    for day in data.get("days", []):
        for row in day.get("rows", []):
            symbol = (row.get("symbol") or row.get("ticker") or "").strip().upper()
            info = ticker_map.get(symbol)
            if not info:
                continue
            if info.get("price") is not None:
                row["stockPrice"] = info["price"]
            if info.get("eps_estimate_curr_q") is not None:
                row["epsEstimate"] = info["eps_estimate_curr_q"]
            if info.get("revenue_estimate_curr_q") is not None:
                row["revenueEstimate"] = info["revenue_estimate_curr_q"]
            if info.get("volume") is not None:
                row["tradingVolume"] = info["volume"]
            if info.get("market_cap") is not None:
                row["marketCap"] = info["market_cap"]
            if info.get("pe_ratio") is not None:
                row["peRatio"] = info["pe_ratio"]
            if info.get("year_high") is not None:
                row["yearHigh"] = info["year_high"]
            if info.get("year_low") is not None:
                row["yearLow"] = info["year_low"]
            if info.get("volume") is not None:
                row["tradingVolume"] = info["volume"]

    data["updated_at"] = now_sgt().isoformat()
    serialized = json.dumps(data, indent=2, ensure_ascii=False)
    frontend_path.write_text(serialized, encoding="utf-8")
    LOGGER.info("Updated frontend JSON with enrichment data: %s", frontend_path)

    canonical = Path("src/data/earnings_data.json")
    if canonical != frontend_path:
        canonical.write_text(serialized, encoding="utf-8")
        LOGGER.info("Mirrored enrichment data to %s", canonical)


def enrich_tickers(tickers: Iterable[str], api_key: str, max_concurrency: int = 3, force: bool = False) -> Dict[str, Dict[str, Optional[float]]]:
    tickers = sorted(set(tickers))
    if not tickers:
        raise ValueError("No tickers found in earnings cache.")

    output_path = enrichment_cache_path_for(now_sgt().date())
    if not force:
        latest = latest_enrichment_path()
        if latest and now_sgt() - datetime.fromtimestamp(latest.stat().st_mtime, tz=now_sgt().tzinfo) < ENRICH_MAX_AGE:
            LOGGER.info("Latest enrichment cache is fresh: %s", latest.name)
            payload = json.loads(latest.read_text(encoding="utf-8"))
            update_frontend_json(payload.get("tickers", {}))
            return payload

    results: Dict[str, Dict[str, Optional[float]]] = {}
    with requests.Session() as session:
        for idx, symbol in enumerate(tickers, start=1):
            metrics = fetch_quote(session, api_key, symbol)
            results[symbol] = metrics
            LOGGER.info("Enriched %s/%s ticker %s", idx, len(tickers), symbol)
            time.sleep(random.uniform(*DEFAULT_SLEEP_RANGE))

    payload = {
        "updated_at": now_sgt().isoformat(),
        "source": "Yahoo Finance (RapidAPI quotes)",
        "tickers": results,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    LOGGER.info("Enrichment written to %s (%s tickers)", output_path, len(results))

    update_frontend_json(results)
    return payload


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Yahoo earnings enrichment job")
    parser.add_argument("--force", action="store_true", help="Force refresh even if cache is fresh")
    parser.add_argument("--max-concurrency", type=int, default=3, help="(kept for compatibility; sequential fetch)")
    parser.add_argument("--api-key", help="RapidAPI key (optional, fallback to RAPIDAPI_KEY env or default)")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    api_key = get_api_key(args.api_key)
    tickers = load_cached_tickers()
    if not tickers:
        LOGGER.warning("No tickers discovered from earnings cache. Nothing to do.")
        return

    LOGGER.info("Starting enrichment for %s tickers", len(tickers))
    enrich_tickers(tickers, api_key=api_key, max_concurrency=args.max_concurrency, force=args.force)


if __name__ == "__main__":  # pragma: no cover
    main()
