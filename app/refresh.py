"""Fetch Yahoo Finance earnings calendar via RapidAPI and write frontend JSON."""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .utils import now_sgt, parse_number, parse_start_date

LOGGER = logging.getLogger("app.refresh")
logging.basicConfig(level=logging.INFO)

API_HOST = "yahoo-finance15.p.rapidapi.com"
BASE_URL = f"https://{API_HOST}/api/v1/markets/calendar/earnings"
DEFAULT_API_KEY = "f3ba37d23bmsh7f5f08200423752p124129jsn859ceeb7bbd1"
DATA_DIR = Path("src/data")
DATA_CLIENT_PATH = Path("src/utils/dataClient.js")
DEFAULT_DAYS = 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Yahoo earnings calendar via RapidAPI")
    parser.add_argument("--date", help="Start date YYYY-MM-DD (default: today)")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="Number of consecutive days to fetch")
    parser.add_argument("--api-key", help="RapidAPI key (optional, fallback to RAPIDAPI_KEY env)")
    return parser.parse_args()


def get_api_key(explicit: str | None = None) -> str:
    key = explicit or os.getenv("RAPIDAPI_KEY") or DEFAULT_API_KEY
    if not key:
        raise ValueError("RapidAPI key missing. Set RAPIDAPI_KEY or use --api-key.")
    return key


def fetch_day(session: requests.Session, key: str, target_date: date) -> dict:
    params = {"date": target_date.isoformat()}
    headers = {
        "x-rapidapi-key": key,
        "x-rapidapi-host": API_HOST,
        "accept": "application/json",
    }
    LOGGER.info("Fetching earnings calendar for %s", target_date.isoformat())
    response = session.get(BASE_URL, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def collect_rows(obj: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    def _collect(current: Any) -> None:
        if isinstance(current, dict):
            symbol = current.get("symbol") or current.get("ticker")
            if symbol and not any(isinstance(current.get(k), list) for k in ("data", "earnings")):
                rows.append(current)
            else:
                for value in current.values():
                    _collect(value)
        elif isinstance(current, list):
            for item in current:
                _collect(item)

    _collect(obj)
    return rows




def extract_metrics_from_raw(raw: dict) -> Dict[str, Optional[float]]:
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
    high_keys = {"fiftytwoweekhigh", "52weekhigh", "week52high", "fiftytwo_weekhigh", "fiftytwo_weekhi"}
    low_keys = {"fiftytwoweeklow", "52weeklow", "week52low", "fiftytwo_weeklow", "fiftytwo_weeklo"}

    def flatten(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k, v
                yield from flatten(v)
        elif isinstance(obj, list):
            for item in obj:
                yield from flatten(item)

    for key, value in flatten(raw):
        if not isinstance(key, str):
            continue
        normalized = key.lower()
        if price is None and (normalized in price_keys or "price" in normalized):
            price = parse_number(value)
        elif eps is None and (normalized in eps_keys or "eps" in normalized):
            eps = parse_number(value)
        elif revenue is None and (normalized in revenue_keys or "revenue" in normalized):
            revenue = parse_number(value)
        elif volume is None and (normalized in volume_keys or "volume" in normalized):
            volume = parse_number(value)
        elif market_cap is None and (normalized in market_cap_keys or "marketcap" in normalized):
            market_cap = parse_number(value)
        elif pe_ratio is None and (normalized in pe_keys or ("pe" in normalized and "peg" not in normalized)):
            pe_ratio = parse_number(value)
        elif year_high is None and (normalized in high_keys or ("high" in normalized and "52" in normalized)):
            year_high = parse_number(value)
        elif year_low is None and (normalized in low_keys or ("low" in normalized and "52" in normalized)):
            year_low = parse_number(value)

    return {
        "stockPrice": price,
        "epsEstimate": eps,
        "revenueEstimate": revenue,
        "tradingVolume": volume,
        "marketCap": market_cap,
        "peRatio": pe_ratio,
        "yearHigh": year_high,
        "yearLow": year_low,
    }

def transform_row(raw: Dict[str, Any], fallback_time: str | None = None) -> Dict[str, Any]:
    symbol = (raw.get("symbol") or raw.get("ticker") or raw.get("instrument") or "").strip().upper()
    company = raw.get("company") or raw.get("companyshortname") or raw.get("name") or symbol
    eps_estimate = raw.get("epsestimate") or raw.get("epsEstimate")
    eps_reported = raw.get("epsactual") or raw.get("epsActual") or raw.get("epsreported")
    surprise_pct = (
        raw.get("epssurprisepct")
        or raw.get("epsSurprisePct")
        or raw.get("surprisepct")
        or raw.get("surprisePercent")
    )
    time_field = raw.get("time") or raw.get("starttime") or raw.get("startdatetimetype") or fallback_time or "-"
    metrics = extract_metrics_from_raw(raw)

    return {
        "symbol": symbol,
        "company": company,
        "eps_estimate": eps_estimate,
        "eps_reported": eps_reported,
        "surprise_pct": surprise_pct,
        "time": time_field,
        "quote_url": f"https://finance.yahoo.com/quote/{symbol}/" if symbol else None,
        "epsEstimate": metrics["epsEstimate"],
        "revenueEstimate": metrics["revenueEstimate"],
        "stockPrice": metrics["stockPrice"],
        "tradingVolume": metrics["tradingVolume"],
        "marketCap": metrics["marketCap"],
        "peRatio": metrics["peRatio"],
        "yearHigh": metrics["yearHigh"],
        "yearLow": metrics["yearLow"],
    }


def build_day_payload(target_date: date, raw_payload: dict) -> Dict[str, Any]:
    rows = collect_rows(raw_payload)
    transformed = [transform_row(item, raw_payload.get("time")) for item in rows]
    return {
        "day": target_date.isoformat(),
        "url": f"https://finance.yahoo.com/calendar/earnings?day={target_date.isoformat()}",
        "count": len(transformed),
        "rows": transformed,
        "error": None if transformed else "No earnings returned",
    }


def write_json(payload: dict, start: date, end: date) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if start == end:
        filename = f"earnings_data_{start.isoformat()}.json"
    else:
        filename = f"earnings_data_{start.isoformat()}_{end.isoformat()}.json"
    output_path = DATA_DIR / filename
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    output_path.write_text(serialized, encoding="utf-8")
    LOGGER.info("Wrote %s", output_path)

    # For compatibility, also update canonical file
    canonical = DATA_DIR / "earnings_data.json"
    canonical.write_text(serialized, encoding="utf-8")
    LOGGER.info("Updated %s", canonical)

    # Persist a copy under cache for historical reference
    cache_dir = Path("cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / filename
    cache_file.write_text(serialized, encoding="utf-8")
    LOGGER.info("Wrote cache copy %s", cache_file)

    return output_path


def update_data_client(target_filename: str) -> None:
    if not DATA_CLIENT_PATH.exists():
        return
    lines = DATA_CLIENT_PATH.read_text(encoding="utf-8").splitlines()
    import_line = f'import earningsData from "../data/{target_filename}";'
    if lines:
        lines[0] = import_line
    else:
        lines = [import_line]
    DATA_CLIENT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOGGER.info("Updated %s to reference %s", DATA_CLIENT_PATH, target_filename)


def main() -> None:
    args = parse_args()
    api_key = get_api_key(args.api_key)
    start_date = parse_start_date(args.date)
    window_days = max(1, args.days)
    end_date = start_date + timedelta(days=window_days - 1)

    days_payload = []
    with requests.Session() as session:
        for offset in range(window_days):
            current_date = start_date + timedelta(days=offset)
            try:
                raw = fetch_day(session, api_key, current_date)
                day_payload = build_day_payload(current_date, raw)
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Failed to fetch %s: %s", current_date, exc)
                day_payload = {
                    "day": current_date.isoformat(),
                    "url": f"https://finance.yahoo.com/calendar/earnings?day={current_date.isoformat()}",
                    "count": 0,
                    "rows": [],
                    "error": str(exc),
                }
            days_payload.append(day_payload)

    payload = {
        "params": {"start_day": start_date.isoformat(), "end_day": end_date.isoformat()},
        "updated_at": now_sgt().isoformat(),
        "source": "Yahoo Finance (RapidAPI)",
        "days": days_payload,
    }

    output_path = write_json(payload, start_date, end_date)
    update_data_client(output_path.name)
    LOGGER.info("Done. Frontend now references %s", output_path.name)


if __name__ == "__main__":  # pragma: no cover
    main()
