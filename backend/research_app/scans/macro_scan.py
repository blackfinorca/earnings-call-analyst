#!/usr/bin/env python3
"""Macro scan — fetches live market and economic data via yfinance and FRED."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import yfinance as yf


BASE_DIR = Path(__file__).resolve().parents[3]
PHASE_DIR = BASE_DIR / "M1 macro scan"
DATA_DIR = BASE_DIR / "data"
ENV_PATH = BASE_DIR / ".env"

DEFAULT_OUTPUT_PATH = PHASE_DIR / "research-macro-scan.json"
CACHE_PATH = DATA_DIR / "state" / "macro-cache.json"

FRED_BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
BLS_BASE_URL  = "https://api.bls.gov/publicAPI/v1/timeseries/data"

# Cache TTLs in minutes
TTL_MARKET   = 15      # indices, commodities, yields
TTL_ECONOMIC = 1440    # CPI, GDP, PMI (daily release cadence)
TTL_WEEKLY   = 10080   # initial claims (weekly release)

RATE_LIMIT_SECONDS = 0.3   # pause between yfinance calls


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def direction(current: float | None, prior: float | None) -> str | None:
    if current is None or prior is None:
        return None
    if current > prior:
        return "up"
    if current < prior:
        return "down"
    return "flat"


def fmt_price(v: float | None, digits: int = 2) -> str | None:
    if v is None:
        return None
    return f"{v:,.{digits}f}"


def fmt_pct(v: float | None, digits: int = 2) -> str | None:
    if v is None:
        return None
    return f"{v:.{digits}f}%"


def pct_change(current: float, prior: float | None) -> float | None:
    if prior and prior != 0:
        return (current - prior) / abs(prior) * 100
    return None


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")


def cache_get(cache: dict, key: str, ttl_minutes: int) -> Any | None:
    entry = cache.get(key)
    if not entry:
        return None
    try:
        fetched = datetime.fromisoformat(entry["fetched_at"])
        if utc_now() - fetched <= timedelta(minutes=ttl_minutes):
            return entry["data"]
    except Exception:
        pass
    return None


def cache_set(cache: dict, key: str, data: Any) -> None:
    cache[key] = {"fetched_at": utc_now().isoformat(), "data": data}


# ---------------------------------------------------------------------------
# yfinance fetcher — market prices
# ---------------------------------------------------------------------------

def fetch_yf(symbol: str, cache: dict, ttl: int = TTL_MARKET, period: str = "5d") -> dict | None:
    key = f"yf:{symbol}"
    cached = cache_get(cache, key, ttl)
    if cached:
        return cached

    try:
        hist = yf.Ticker(symbol).history(period=period, auto_adjust=True)
        if hist.empty:
            time.sleep(RATE_LIMIT_SECONDS)
            hist = yf.download(symbol, period=period, auto_adjust=True, progress=False, multi_level_index=False)
        if hist.empty:
            return None

        current = float(hist["Close"].iloc[-1])
        prior   = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else None
        as_of   = hist.index[-1].to_pydatetime().replace(tzinfo=timezone.utc).isoformat()

        data = {"current": current, "prior": prior, "as_of": as_of}
        cache_set(cache, key, data)
        time.sleep(RATE_LIMIT_SECONDS)
        return data
    except Exception as exc:
        print(f"  [yfinance] {symbol}: {exc}")
        return None


# ---------------------------------------------------------------------------
# FRED CSV fetcher — economic indicators
# ---------------------------------------------------------------------------

def fetch_fred(series_id: str, cache: dict, ttl: int = TTL_ECONOMIC, limit: int = 14) -> list[dict] | None:
    key = f"fred:{series_id}"
    cached = cache_get(cache, key, ttl)
    if cached:
        return cached

    url = f"{FRED_BASE_URL}?id={series_id}"
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; macro-scan/1.0)"})
        with urlopen(req, timeout=8) as resp:
            text = resp.read().decode("utf-8")
    except Exception as exc:
        print(f"  [FRED] {series_id}: {exc}")
        return None
    try:
        rows: list[dict] = []
        for row in csv.DictReader(io.StringIO(text)):
            date = row.get("DATE", "")
            val_str = row.get("VALUE", "").strip()
            if val_str and val_str != ".":
                try:
                    rows.append({"date": date, "value": float(val_str)})
                except ValueError:
                    pass

        rows = sorted(rows, key=lambda r: r["date"], reverse=True)[:limit]
        if rows:
            cache_set(cache, key, rows)
        return rows or None
    except Exception as exc:
        print(f"  [FRED] {series_id}: {exc}")
        return None


def fetch_bls(series_id: str, cache: dict, ttl: int = TTL_ECONOMIC) -> list[dict] | None:
    """Fetch a BLS V1 series (no API key required). Returns newest-first {date, value} list."""
    key = f"bls:{series_id}"
    cached = cache_get(cache, key, ttl)
    if cached:
        return cached

    url = f"{BLS_BASE_URL}/{series_id}"
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; macro-scan/1.0)"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"  [BLS] {series_id}: {exc}")
        return None

    if data.get("status") != "REQUEST_SUCCEEDED":
        print(f"  [BLS] {series_id}: {data.get('message', 'request failed')}")
        return None

    rows: list[dict] = []
    for item in data["Results"]["series"][0]["data"]:
        period = item.get("period", "")
        if not period.startswith("M") or period == "M13":
            continue  # skip annual averages
        val_str = item.get("value", "").strip()
        if not val_str or val_str in {"-", ""}:
            continue
        try:
            month = period[1:]  # "M02" → "02"
            date_str = f"{item['year']}-{month}"
            rows.append({"date": date_str, "value": float(val_str)})
        except (ValueError, KeyError):
            pass

    rows = sorted(rows, key=lambda r: r["date"], reverse=True)
    if rows:
        cache_set(cache, key, rows)
    return rows or None


def fred_pair(rows: list[dict] | None) -> tuple[float | None, float | None, str | None]:
    """Return (current, prior, date) from FRED rows (newest-first)."""
    if not rows:
        return None, None, None
    cur  = rows[0]["value"]
    pri  = rows[1]["value"] if len(rows) >= 2 else None
    date = rows[0]["date"]
    return cur, pri, date


# ---------------------------------------------------------------------------
# Row factory
# ---------------------------------------------------------------------------

def make_row(
    data_point: str,
    current_value: str | None,
    prior_reading: str | None,
    dir_: str | None,
    signal: str,
    status: str,
    provider: str,
    symbol: str,
    note: str = "",
) -> dict:
    source: dict[str, Any] = {"provider": provider, "symbol": symbol}
    if note:
        source["note"] = note
    return {
        "data_point": data_point,
        "current_value": current_value,
        "prior_reading": prior_reading,
        "direction": dir_,
        "signal_implication": signal,
        "status": status,
        "source": source,
    }


def unavailable_row(data_point: str, note: str = "") -> dict:
    return make_row(data_point, None, None, None, "Data unavailable.", "unavailable", "—", "—", note)


# ---------------------------------------------------------------------------
# Row builders — market / prices (yfinance)
# ---------------------------------------------------------------------------

def build_index_row(name: str, symbol: str, cache: dict, digits: int = 2) -> dict:
    d = fetch_yf(symbol, cache)
    if not d:
        return unavailable_row(name)
    cur, pri = d["current"], d["prior"]
    dir_ = direction(cur, pri)
    pct  = pct_change(cur, pri)
    pct_str = f" ({pct:+.2f}%)" if pct is not None else ""
    signal = {
        "up":   f"Positive momentum{pct_str}; risk appetite supported.",
        "down": f"Selling pressure{pct_str}; risk-off conditions.",
    }.get(dir_ or "", "Flat; no directional signal.")
    return make_row(name, fmt_price(cur, digits), fmt_price(pri, digits), dir_, signal,
                    "ok", "Yahoo Finance / yfinance", symbol, d["as_of"])


def build_vix_row(cache: dict) -> dict:
    d = fetch_yf("^VIX", cache)
    if not d:
        return unavailable_row("VIX")
    cur, pri = d["current"], d["prior"]
    dir_ = direction(cur, pri)
    if cur >= 30:
        signal = f"VIX {cur:.1f} — extreme fear; market expects sharp near-term moves."
    elif cur >= 20:
        signal = f"VIX {cur:.1f} — elevated uncertainty; hedging demand rising."
    else:
        signal = f"VIX {cur:.1f} — calm; low realized volatility priced in."
    return make_row("VIX", fmt_price(cur, 2), fmt_price(pri, 2), dir_, signal,
                    "ok", "Yahoo Finance / yfinance", "^VIX", d["as_of"])


def build_wti_row(cache: dict) -> dict:
    d = fetch_yf("CL=F", cache)
    if not d:
        return unavailable_row("WTI Crude Oil")
    cur, pri = d["current"], d["prior"]
    dir_ = direction(cur, pri)
    if cur >= 90:
        signal = f"WTI ${cur:.1f} — high; inflation pressure, demand squeeze for consumers."
    elif cur >= 70:
        signal = f"WTI ${cur:.1f} — moderate; balanced supply/demand."
    else:
        signal = f"WTI ${cur:.1f} — low; deflationary signal, demand concerns."
    return make_row("WTI Crude Oil", fmt_price(cur, 1), fmt_price(pri, 1), dir_, signal,
                    "ok", "Yahoo Finance / yfinance", "CL=F", d["as_of"])


def build_gold_row(cache: dict) -> dict:
    d = fetch_yf("GC=F", cache)
    if not d:
        return unavailable_row("Gold Price")
    cur, pri = d["current"], d["prior"]
    dir_ = direction(cur, pri)
    signal = {
        "up":   f"Gold ${cur:,.0f} rising — safe-haven demand; inflation or tail-risk hedging active.",
        "down": f"Gold ${cur:,.0f} falling — risk appetite improving or dollar strengthening.",
    }.get(dir_ or "", f"Gold ${cur:,.0f} stable.")
    return make_row("Gold Price", fmt_price(cur, 0), fmt_price(pri, 0), dir_, signal,
                    "ok", "Yahoo Finance / yfinance", "GC=F", d["as_of"])


def build_dxy_row(cache: dict) -> dict:
    d = fetch_yf("DX-Y.NYB", cache) or fetch_yf("DX=F", cache)
    if not d:
        return unavailable_row("DXY Dollar Index")
    cur, pri = d["current"], d["prior"]
    dir_ = direction(cur, pri)
    pct = pct_change(cur, pri)
    pct_str = f" ({pct:+.2f}%)" if pct is not None else ""
    signal = {
        "up":   f"Dollar strengthening{pct_str}; headwind for commodities and EM assets.",
        "down": f"Dollar weakening{pct_str}; tailwind for commodities and international equities.",
    }.get(dir_ or "", f"Dollar stable{pct_str}.")
    return make_row("DXY Dollar Index", fmt_price(cur, 2), fmt_price(pri, 2), dir_, signal,
                    "ok", "Yahoo Finance / yfinance", "DX-Y.NYB", d["as_of"])


# ---------------------------------------------------------------------------
# Row builders — rates / yields (FRED)
# ---------------------------------------------------------------------------

def build_fed_funds_row(cache: dict) -> dict:
    # ^IRX = 13-week T-bill, the closest real-time proxy for Fed Funds on Yahoo Finance
    d = fetch_yf("^IRX", cache)
    if not d:
        return unavailable_row("Fed Funds Rate")
    cur, pri = d["current"], d["prior"]
    dir_ = direction(cur, pri)
    if cur >= 5.0:
        signal = f"Fed Funds ~{cur:.2f}% — restrictive; credit conditions tight."
    elif cur >= 3.0:
        signal = f"Fed Funds ~{cur:.2f}% — moderately restrictive; above neutral."
    else:
        signal = f"Fed Funds ~{cur:.2f}% — accommodative; supportive financial conditions."
    return make_row("Fed Funds Rate", fmt_pct(cur), fmt_pct(pri), dir_, signal,
                    "ok", "Yahoo Finance / yfinance", "^IRX", "13-week T-bill proxy")


def build_10y_row(cache: dict) -> dict:
    # ^TNX = CBOE 10-Year Treasury Note Yield on Yahoo Finance (value already in %)
    d = fetch_yf("^TNX", cache)
    if not d:
        return unavailable_row("10Y Treasury Yield")
    cur, pri = d["current"], d["prior"]
    dir_ = direction(cur, pri)
    signal = {
        "up":   f"10Y yield rising ({cur:.2f}%); tighter financial conditions, valuation pressure on equities.",
        "down": f"10Y yield falling ({cur:.2f}%); easing conditions, growth expectations softening.",
    }.get(dir_ or "", f"10Y yield stable ({cur:.2f}%).")
    return make_row("10Y Treasury Yield", fmt_pct(cur), fmt_pct(pri), dir_, signal,
                    "ok", "Yahoo Finance / yfinance", "^TNX", d["as_of"])


def build_2y_row(cache: dict) -> dict:
    # Try Yahoo Finance tickers for 2Y, then fall back to FRED
    d = fetch_yf("2YY=F", cache) or fetch_yf("^TUO", cache)
    if d:
        cur, pri = d["current"], d["prior"]
        provider, symbol, note = "Yahoo Finance / yfinance", "2YY=F", d["as_of"]
    else:
        rows = fetch_fred("DGS2", cache, limit=5)
        cur, pri, date = fred_pair(rows)
        if cur is None:
            return unavailable_row("2Y Treasury Yield")
        provider, symbol, note = "FRED", "DGS2", f"as of {date}"
    dir_ = direction(cur, pri)
    signal = {
        "up":   f"2Y yield rising ({cur:.2f}%); market pricing more Fed hikes or higher-for-longer.",
        "down": f"2Y yield falling ({cur:.2f}%); market pricing rate cuts ahead.",
    }.get(dir_ or "", f"2Y yield stable ({cur:.2f}%).")
    return make_row("2Y Treasury Yield", fmt_pct(cur), fmt_pct(pri), dir_, signal,
                    "ok", provider, symbol, note)


def build_spread_row(ten_y: dict, two_y: dict) -> dict:
    try:
        cur_10 = float(ten_y["current_value"].rstrip("%"))
        cur_2  = float(two_y["current_value"].rstrip("%"))
        spread = cur_10 - cur_2
        prior_spread: float | None = None
        if ten_y["prior_reading"] and two_y["prior_reading"]:
            prior_spread = float(ten_y["prior_reading"].rstrip("%")) - float(two_y["prior_reading"].rstrip("%"))
        dir_ = direction(spread, prior_spread)
        if spread < 0:
            signal = f"Yield curve inverted ({spread:+.2f}%); historically precedes recession."
        elif spread < 0.5:
            signal = f"Yield curve flat ({spread:+.2f}%); limited growth confidence."
        else:
            signal = f"Yield curve normal ({spread:+.2f}%); growth expectations intact."
        return make_row("10Y-2Y Spread", fmt_pct(spread), fmt_pct(prior_spread), dir_, signal,
                        "derived", "Derived", "DGS10 − DGS2", "Computed from FRED series")
    except Exception:
        return unavailable_row("10Y-2Y Spread", "Failed to compute from 10Y and 2Y rows")


# ---------------------------------------------------------------------------
# Row builders — economic indicators (FRED)
# ---------------------------------------------------------------------------

def build_cpi_row(cache: dict) -> dict:
    rows = fetch_bls("CUUR0000SA0", cache)
    if not rows or len(rows) < 13:
        return unavailable_row("CPI YoY")
    cur_yoy = (rows[0]["value"] / rows[12]["value"] - 1) * 100
    pri_yoy = (rows[1]["value"] / rows[13]["value"] - 1) * 100 if len(rows) >= 14 else None
    dir_ = direction(cur_yoy, pri_yoy)
    if cur_yoy >= 4:
        signal = f"CPI {cur_yoy:.1f}% YoY — well above 2% target; inflation primary concern."
    elif cur_yoy >= 2.5:
        signal = f"CPI {cur_yoy:.1f}% YoY — above target; disinflation progress stalling."
    else:
        signal = f"CPI {cur_yoy:.1f}% YoY — approaching 2% target; inflation receding."
    return make_row("CPI YoY", fmt_pct(cur_yoy, 1), fmt_pct(pri_yoy, 1) if pri_yoy else None, dir_, signal,
                    "ok", "BLS", "CUUR0000SA0", f"as of {rows[0]['date']}")


def build_core_pce_row(cache: dict) -> dict:
    rows = fetch_fred("PCEPILFE", cache, limit=15)
    if not rows or len(rows) < 13:
        return unavailable_row("Core PCE YoY")
    cur_yoy = (rows[0]["value"] / rows[12]["value"] - 1) * 100
    pri_yoy = (rows[1]["value"] / rows[13]["value"] - 1) * 100 if len(rows) >= 14 else None
    dir_ = direction(cur_yoy, pri_yoy)
    above = cur_yoy >= 2.5
    signal = (
        f"Core PCE {cur_yoy:.1f}% YoY — Fed's preferred gauge; "
        + ("above 2.5%, policy stays restrictive." if above else "approaching 2% target.")
    )
    return make_row("Core PCE YoY", fmt_pct(cur_yoy, 1), fmt_pct(pri_yoy, 1) if pri_yoy else None, dir_, signal,
                    "ok", "FRED", "PCEPILFE", f"as of {rows[0]['date']}")


def build_mfg_pmi_row(cache: dict) -> dict:
    rows = fetch_fred("MFGPMNSA", cache, limit=3)
    cur, pri, date = fred_pair(rows)
    if cur is None:
        return unavailable_row("ISM Manufacturing PMI")
    dir_ = direction(cur, pri)
    signal = (
        f"PMI {cur:.1f} — manufacturing {'expanding' if cur >= 50 else 'contracting'}; "
        + ("industrial demand supported." if cur >= 50 else "industrial headwinds.")
    )
    return make_row("ISM Manufacturing PMI", fmt_price(cur, 1), fmt_price(pri, 1), dir_, signal,
                    "ok", "FRED", "MFGPMNSA", f"as of {date}")


def build_svc_pmi_row(cache: dict) -> dict:
    rows = fetch_fred("NMFCI", cache, limit=3)
    cur, pri, date = fred_pair(rows)
    if cur is None:
        return unavailable_row("ISM Services PMI", "FRED NMFCI series unavailable")
    dir_ = direction(cur, pri)
    signal = (
        f"Services NMI {cur:.1f} — services {'expanding' if cur >= 50 else 'contracting'}; "
        + ("consumer demand holding." if cur >= 50 else "demand softening.")
    )
    return make_row("ISM Services PMI", fmt_price(cur, 1), fmt_price(pri, 1), dir_, signal,
                    "ok", "FRED", "NMFCI", f"as of {date}")


def build_unemployment_row(cache: dict) -> dict:
    rows = fetch_bls("LNS14000000", cache)
    cur, pri, date = fred_pair(rows)  # same shape: newest-first {date, value}
    if cur is None:
        return unavailable_row("Unemployment Rate")
    dir_ = direction(cur, pri)
    if cur <= 4.0:
        signal = f"Unemployment {cur:.1f}% — tight labor market; wage pressure persists."
    elif cur <= 5.0:
        signal = f"Unemployment {cur:.1f}% — near full employment; modest slack emerging."
    else:
        signal = f"Unemployment {cur:.1f}% — labor market loosening; demand risk rising."
    return make_row("Unemployment Rate", fmt_pct(cur, 1), fmt_pct(pri, 1), dir_, signal,
                    "ok", "BLS", "LNS14000000", f"as of {date}")


def build_claims_row(cache: dict) -> dict:
    rows = fetch_fred("ICSA", cache, ttl=TTL_WEEKLY, limit=3)
    cur, pri, date = fred_pair(rows)
    if cur is None:
        return unavailable_row("Initial Jobless Claims")
    dir_ = direction(cur, pri)
    cur_k = cur / 1_000
    pri_k = pri / 1_000 if pri else None
    if cur >= 300_000:
        signal = f"Claims {cur_k:.0f}k — rising filings; labor market deteriorating."
    elif cur >= 250_000:
        signal = f"Claims {cur_k:.0f}k — elevated; monitoring for trend."
    else:
        signal = f"Claims {cur_k:.0f}k — historically low; labor market resilient."
    return make_row("Initial Jobless Claims", f"{cur_k:.0f}k", f"{pri_k:.0f}k" if pri_k else None, dir_, signal,
                    "ok", "FRED", "ICSA", f"as of {date}")


def build_gdp_row(cache: dict) -> dict:
    rows = fetch_fred("A191RL1Q225SBEA", cache, limit=3)
    cur, pri, date = fred_pair(rows)
    if cur is None:
        return unavailable_row("US GDP")
    dir_ = direction(cur, pri)
    if cur >= 2.5:
        signal = f"Real GDP {cur:.2f}% annualized — solid growth; soft-landing narrative supported."
    elif cur >= 0:
        signal = f"Real GDP {cur:.2f}% annualized — stalling growth; stagflation risk elevated."
    else:
        signal = f"Real GDP {cur:.2f}% annualized — contraction; recession risk rising."
    return make_row("US GDP", fmt_pct(cur, 2), fmt_pct(pri, 2), dir_, signal,
                    "ok", "FRED", "A191RL1Q225SBEA", f"quarterly annualized, as of {date}")


# ---------------------------------------------------------------------------
# Assembler
# ---------------------------------------------------------------------------

def build_macro_scan_payload(force_refresh: bool = False) -> dict:
    cache = {} if force_refresh else load_cache()

    print("  Fetching market data (yfinance)...")
    sp500  = build_index_row("S&P 500",       "^GSPC",     cache)
    nasdaq = build_index_row("Nasdaq",         "^IXIC",     cache)
    rut    = build_index_row("Russell 2000",   "^RUT",      cache)
    vix    = build_vix_row(cache)
    wti    = build_wti_row(cache)
    gold   = build_gold_row(cache)
    dxy    = build_dxy_row(cache)

    print("  Fetching yield / rate data (yfinance + FRED)...")
    fed    = build_fed_funds_row(cache)
    ten_y  = build_10y_row(cache)
    two_y  = build_2y_row(cache)
    spread = build_spread_row(ten_y, two_y)

    print("  Fetching economic indicators (FRED)...")
    cpi    = build_cpi_row(cache)
    pce    = build_core_pce_row(cache)
    mfg    = build_mfg_pmi_row(cache)
    svc    = build_svc_pmi_row(cache)
    unemp  = build_unemployment_row(cache)
    claims = build_claims_row(cache)
    gdp    = build_gdp_row(cache)

    save_cache(cache)

    rows = [
        sp500, nasdaq, rut, vix,
        fed, ten_y, two_y, spread,
        cpi, pce, mfg, svc,
        unemp, claims,
        wti, gold, dxy,
        gdp,
    ]

    limitations  = [r["data_point"] for r in rows if r["status"] == "unavailable"]
    proxy_rows   = [r["data_point"] for r in rows if r["status"] == "proxy"]
    derived_rows = [r["data_point"] for r in rows if r["status"] == "derived"]

    return {
        "function": "research-macro-scan",
        "generated_at": utc_now().isoformat(),
        "providers": ["Yahoo Finance / yfinance", "BLS (Bureau of Labor Statistics)", "FRED (Federal Reserve Economic Data)"],
        "rows": rows,
        "limitations": limitations,
        "proxy_rows": proxy_rows,
        "derived_rows": derived_rows,
    }


# ---------------------------------------------------------------------------
# Public API (imported by research-functions.py)
# ---------------------------------------------------------------------------

def research_macro_scan(output: str | None = None, force_refresh: bool = False, **_kwargs: Any) -> dict:
    payload = build_macro_scan_payload(force_refresh=force_refresh)
    out_path = Path(output) if output else DEFAULT_OUTPUT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


API_FUNCTIONS: dict[str, Any] = {
    "research-macro-scan": research_macro_scan,
}


def invoke_api_function(name: str, **kwargs: Any) -> dict:
    if name not in API_FUNCTIONS:
        raise ValueError(f"Unknown function: {name!r}. Available: {list(API_FUNCTIONS)}")
    return API_FUNCTIONS[name](**kwargs)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the M1 macro scan via yfinance and FRED."
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="research-macro-scan",
        choices=list(API_FUNCTIONS),
        help="Function to invoke (default: research-macro-scan).",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Output JSON file path.",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Bypass cache and re-fetch all data.",
    )
    return parser.parse_args()


def main() -> None:
    load_env_file(ENV_PATH)
    args = parse_args()

    print(f"[macro-scan] Starting (yfinance + FRED)", flush=True)
    payload = invoke_api_function(
        args.command,
        output=args.output,
        force_refresh=args.force_refresh,
    )

    ok  = sum(1 for r in payload["rows"] if r["status"] == "ok")
    bad = sum(1 for r in payload["rows"] if r["status"] == "unavailable")
    print(f"\n  {ok} rows OK, {bad} unavailable")
    if payload["limitations"]:
        print(f"  Unavailable: {', '.join(payload['limitations'])}")
    print(f"\n  Output: {args.output}")
    print(json.dumps({"output_file": args.output, "rows": len(payload["rows"])}, indent=2))


if __name__ == "__main__":
    main()
