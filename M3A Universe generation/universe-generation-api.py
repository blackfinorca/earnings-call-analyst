#!/usr/bin/env python3
"""M3b Input Builder — fetch fundamentals and technicals via yfinance for every
ticker in universe-generation.json and write universe-generation-api.json."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf


BASE_DIR   = Path(__file__).resolve().parent
ENV_PATH   = BASE_DIR.parent / ".env"
INPUT_PATH = BASE_DIR / "universe-generation.json"
OUTPUT_PATH = BASE_DIR / "universe-generation-api.json"

CACHE_TTL_DAYS     = 7
RATE_LIMIT_SECONDS = 0.3   # yfinance / Yahoo rate limit buffer
RETRY_DELAY        = 2.0   # seconds to wait before a single retry


# ---------------------------------------------------------------------------
# Env loader
# ---------------------------------------------------------------------------

class RunnerError(RuntimeError):
    """Fatal runner error."""


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


# ---------------------------------------------------------------------------
# Safe helpers
# ---------------------------------------------------------------------------

def sv(info: dict, key: str, default=None):
    """Safe value — return None for sentinel non-values."""
    val = info.get(key, default)
    return val if val not in [None, "None", float("inf"), float("-inf"), "N/A", ""] else default


def pct_val(info: dict, key: str) -> float | None:
    """Return a ratio field multiplied to percentage, or None."""
    val = sv(info, key)
    return round(val * 100, 2) if val is not None else None


def safe_div(a, b, ndigits: int = 2) -> float | None:
    try:
        if a is None or b is None or b == 0:
            return None
        return round(a / b, ndigits)
    except (TypeError, ZeroDivisionError):
        return None


# ---------------------------------------------------------------------------
# Technicals — yfinance price history, primary + fallback
# ---------------------------------------------------------------------------

def _compute_technicals(close: list, volume: list, high: list, low: list) -> dict | None:
    """Compute all technical indicators from OHLCV lists (ascending order)."""
    n = len(close)
    if n < 200:
        return None

    price_current  = round(close[-1], 2)
    price_1m_ago   = round(close[max(n - 21,  0)], 2)
    price_3m_ago   = round(close[max(n - 63,  0)], 2)
    price_6m_ago   = round(close[max(n - 126, 0)], 2)
    price_12m_ago  = round(close[max(n - 252, 0)], 2)

    return_1m_pct  = round((price_current / price_1m_ago  - 1) * 100, 2)
    return_3m_pct  = round((price_current / price_3m_ago  - 1) * 100, 2)
    return_6m_pct  = round((price_current / price_6m_ago  - 1) * 100, 2)
    return_12m_pct = round((price_current / price_12m_ago - 1) * 100, 2)
    momentum_score = round(return_12m_pct - return_1m_pct, 2)

    ma_20d  = round(sum(close[-20:])  / 20,  2)
    ma_50d  = round(sum(close[-50:])  / 50,  2)
    ma_200d = round(sum(close[-200:]) / 200, 2)

    price_vs_ma50_pct  = round((price_current / ma_50d  - 1) * 100, 2)
    price_vs_ma200_pct = round((price_current / ma_200d - 1) * 100, 2)
    golden_cross       = bool(ma_50d > ma_200d)

    # RSI 14
    deltas     = [close[i] - close[i - 1] for i in range(1, n)]
    gains      = [max(d, 0)  for d in deltas[-14:]]
    losses_raw = [max(-d, 0) for d in deltas[-14:]]
    avg_gain   = sum(gains) / 14
    avg_loss   = sum(losses_raw) / 14
    rsi_14d    = round(100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss != 0 else 100, 2)

    # ATR 14
    hl_ranges  = [high[i] - low[i] for i in range(n)]
    atr_14d    = round(sum(hl_ranges[-14:]) / 14, 2)
    atr_pct    = round(atr_14d / price_current * 100, 2)

    # Volume
    avg_volume_30d = round(sum(volume[-30:]) / 30, 0)
    avg_volume_90d = round(sum(volume[-90:]) / 90, 0)
    volume_trend   = round(avg_volume_30d / avg_volume_90d, 2) if avg_volume_90d > 0 else None

    # 52-week high / low
    week_52_high = round(max(close[-252:]), 2)
    week_52_low  = round(min(close[-252:]), 2)

    return {
        "price_current":       price_current,
        "price_1m_ago":        price_1m_ago,
        "price_3m_ago":        price_3m_ago,
        "price_6m_ago":        price_6m_ago,
        "price_12m_ago":       price_12m_ago,
        "return_1m_pct":       return_1m_pct,
        "return_3m_pct":       return_3m_pct,
        "return_6m_pct":       return_6m_pct,
        "return_12m_pct":      return_12m_pct,
        "momentum_score":      momentum_score,
        "ma_20d":              ma_20d,
        "ma_50d":              ma_50d,
        "ma_200d":             ma_200d,
        "price_vs_ma50_pct":   price_vs_ma50_pct,
        "price_vs_ma200_pct":  price_vs_ma200_pct,
        "golden_cross":        golden_cross,
        "rsi_14d":             rsi_14d,
        "atr_14d":             atr_14d,
        "atr_pct_of_price":    atr_pct,
        "avg_volume_30d":      avg_volume_30d,
        "avg_volume_90d":      avg_volume_90d,
        "volume_trend":        volume_trend,
        "week_52_high":        week_52_high,
        "week_52_low":         week_52_low,
        "support_level":       week_52_low,
        "resistance_level":    week_52_high,
    }


def _history_to_ohlcv(hist) -> tuple[list, list, list, list] | None:
    """Extract clean OHLCV lists from a yfinance history DataFrame."""
    if hist is None or hist.empty:
        return None
    # Drop rows where close or volume is missing
    h = hist.dropna(subset=["Close", "Volume"])
    if h.empty:
        return None
    close  = [float(v) for v in h["Close"].tolist()]
    volume = [float(v) for v in h["Volume"].tolist()]
    high   = [float(v) for v in h["High"].tolist()]
    low    = [float(v) for v in h["Low"].tolist()]
    return close, volume, high, low


def fetch_technicals(symbol: str) -> dict | None:
    """Fetch price history and compute technicals. Retries once on empty result."""
    tk = yf.Ticker(symbol)

    # Primary attempt
    hist = tk.history(period="13mo", auto_adjust=True)
    ohlcv = _history_to_ohlcv(hist)

    if ohlcv is None:
        # Fallback: short pause then retry via yf.download (different code path)
        print(f"  [{symbol}] History empty on first try — retrying via yf.download")
        time.sleep(RETRY_DELAY)
        df = yf.download(
            symbol, period="13mo", auto_adjust=True,
            progress=False, multi_level_index=False,
        )
        ohlcv = _history_to_ohlcv(df)

    if ohlcv is None:
        return None

    close, volume, high, low = ohlcv
    del hist
    return _compute_technicals(close, volume, high, low)


# ---------------------------------------------------------------------------
# Fundamentals — yfinance ticker.info, retries on sparse result
# ---------------------------------------------------------------------------

# Fields that must be present for the info dict to be considered valid
_REQUIRED_INFO_FIELDS = ["marketCap", "totalRevenue", "longName"]


def _info_is_valid(info: dict) -> bool:
    return any(info.get(f) for f in _REQUIRED_INFO_FIELDS)


def fetch_fundamentals(symbol: str) -> dict:
    """Fetch fundamentals from yfinance. Retries once if info is sparse."""
    tk   = yf.Ticker(symbol)
    info = tk.info

    if not _info_is_valid(info):
        print(f"  [{symbol}] Sparse info on first try — retrying after {RETRY_DELAY}s")
        time.sleep(RETRY_DELAY)
        info = yf.Ticker(symbol).info  # fresh object, avoids stale cache

    price   = sv(info, "currentPrice") or sv(info, "regularMarketPrice")
    eps_fwd = sv(info, "forwardEps")
    # pe_forward: prefer computed value; fall back to reported forwardPE
    pe_forward = (
        round(price / eps_fwd, 2)
        if price and eps_fwd and eps_fwd != 0
        else sv(info, "forwardPE")
    )

    return {
        # Identity
        "company_name":            sv(info, "longName"),
        "exchange":                sv(info, "exchange"),
        "sector_gics":             sv(info, "sector"),
        "industry_gics":           sv(info, "industry"),
        "country":                 sv(info, "country"),
        "employees":               sv(info, "fullTimeEmployees"),

        # Market
        "market_cap":              sv(info, "marketCap"),
        "enterprise_value":        sv(info, "enterpriseValue"),
        "avg_volume_30d_info":     sv(info, "averageVolume"),
        "beta":                    sv(info, "beta"),

        # Valuation
        "pe_trailing":             sv(info, "trailingPE"),
        "pe_forward":              pe_forward,
        "peg_ratio":               sv(info, "pegRatio"),
        "price_to_sales":          sv(info, "priceToSalesTrailing12Months"),
        "price_to_book":           sv(info, "priceToBook"),
        "ev_ebitda":               sv(info, "enterpriseToEbitda"),
        "ev_revenue":              sv(info, "enterpriseToRevenue"),

        # Income
        "revenue_ttm":             sv(info, "totalRevenue"),
        "revenue_growth_yoy":      pct_val(info, "revenueGrowth"),
        "gross_margin_pct":        pct_val(info, "grossMargins"),
        "operating_margin_pct":    pct_val(info, "operatingMargins"),
        "net_margin_pct":          pct_val(info, "profitMargins"),
        "ebitda_ttm":              sv(info, "ebitda"),
        "eps_ttm":                 sv(info, "trailingEps"),
        "eps_forward":             eps_fwd,
        "eps_growth_yoy":          pct_val(info, "earningsGrowth"),

        # Balance sheet
        "total_debt":              sv(info, "totalDebt"),
        "cash_and_equivalents":    sv(info, "totalCash"),
        "debt_to_equity":          sv(info, "debtToEquity"),
        "current_ratio":           sv(info, "currentRatio"),

        # Cash flow
        "free_cash_flow_ttm":      sv(info, "freeCashflow"),
        "operating_cf_ttm":        sv(info, "operatingCashflow"),

        # Returns
        "roe":                     pct_val(info, "returnOnEquity"),
        "roa":                     pct_val(info, "returnOnAssets"),

        # Dividends
        "dividend_yield":          pct_val(info, "dividendYield"),
        "payout_ratio":            pct_val(info, "payoutRatio"),

        # Analyst
        "analyst_consensus":       sv(info, "recommendationKey"),
        "analyst_mean_rating":     sv(info, "recommendationMean"),
        "price_target_mean":       sv(info, "targetMeanPrice"),
        "price_target_high":       sv(info, "targetHighPrice"),
        "price_target_low":        sv(info, "targetLowPrice"),

        # Sentiment
        "short_interest_pct":      pct_val(info, "shortPercentOfFloat"),
        "short_ratio":             sv(info, "shortRatio"),
        "institutional_ownership": pct_val(info, "institutionsPercentHeld"),
        "insider_ownership":       pct_val(info, "insidersPercentHeld"),
    }


# ---------------------------------------------------------------------------
# Derived fields
# ---------------------------------------------------------------------------

def compute_derived(fundamentals: dict, technicals: dict) -> dict:
    derived: dict = {}

    debt = fundamentals.get("total_debt") or 0
    cash = fundamentals.get("cash_and_equivalents") or 0
    derived["net_debt"] = debt - cash

    ebitda   = fundamentals.get("ebitda_ttm")
    net_debt = derived["net_debt"]
    derived["debt_to_ebitda"] = (
        round(net_debt / ebitda, 2) if ebitda and ebitda > 0 else None
    )

    fcf    = fundamentals.get("free_cash_flow_ttm")
    mktcap = fundamentals.get("market_cap")
    derived["fcf_yield"] = (
        round(fcf / mktcap * 100, 2) if fcf and mktcap and mktcap > 0 else None
    )

    rev        = fundamentals.get("revenue_ttm")
    net_margin = fundamentals.get("net_margin_pct")
    if rev and net_margin and fcf:
        net_income_approx = rev * (net_margin / 100)
        derived["fcf_to_net_income"] = (
            round(fcf / net_income_approx, 2) if net_income_approx != 0 else None
        )
    else:
        derived["fcf_to_net_income"] = None

    derived["price_to_fcf"] = (
        round(mktcap / fcf, 2) if fcf and fcf > 0 and mktcap else None
    )

    derived["analyst_buy_count"]  = None
    derived["analyst_hold_count"] = None
    derived["analyst_sell_count"] = None

    price  = technicals.get("price_current")
    target = fundamentals.get("price_target_mean")
    derived["price_target_upside_pct"] = (
        round((target / price - 1) * 100, 2) if price and target else None
    )

    atr = technicals.get("atr_14d")
    if price and atr:
        derived["stop_loss_1x_atr"] = round(price - atr, 2)
        derived["stop_loss_2x_atr"] = round(price - (2 * atr), 2)
    else:
        derived["stop_loss_1x_atr"] = None
        derived["stop_loss_2x_atr"] = None

    return derived


# ---------------------------------------------------------------------------
# Hard filter validation
# ---------------------------------------------------------------------------

def validate_filters(fundamentals: dict, technicals: dict) -> dict:
    flags  = []
    passed = True

    mktcap = fundamentals.get("market_cap") or 0
    if mktcap < 2_000_000_000:
        flags.append(f"FAIL: market cap ${mktcap:,.0f} below $2B threshold")
        passed = False

    volume = technicals.get("avg_volume_30d") or 0
    if volume < 500_000:
        flags.append(f"FAIL: avg volume {volume:,.0f} below 500K threshold")
        passed = False

    eps = fundamentals.get("eps_ttm")
    if eps is not None and eps <= 0:
        flags.append(f"FAIL: trailing EPS {eps} — not profitable")
        passed = False

    country = fundamentals.get("country", "") or ""
    if country and country.upper() not in ["UNITED STATES", "US", ""]:
        flags.append(f"WARN: country is {country} — verify US listing")

    return {"passed": passed, "flags": flags}


# ---------------------------------------------------------------------------
# Cache — skip tickers fetched within TTL
# ---------------------------------------------------------------------------

def load_cache(output_path: Path) -> dict[str, dict]:
    """Return ticker → entry for records fetched within CACHE_TTL_DAYS."""
    if not output_path.exists():
        return {}
    try:
        with open(output_path, encoding="utf-8") as f:
            existing = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

    cutoff     = datetime.now(timezone.utc) - timedelta(days=CACHE_TTL_DAYS)
    cache: dict[str, dict] = {}
    all_entries = existing.get("stocks", []) + existing.get("flagged_stocks", [])
    for entry in all_entries:
        fetched_str = entry.get("fetched_at")
        if not fetched_str:
            continue
        try:
            fetched_at = datetime.fromisoformat(fetched_str)
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            if fetched_at > cutoff:
                cache[entry["ticker"]] = entry
        except ValueError:
            continue
    return cache


# ---------------------------------------------------------------------------
# Main fetch loop
# ---------------------------------------------------------------------------

def fetch_all(tickers: list[dict], cache: dict[str, dict]) -> tuple[list, list]:
    results = []
    failed  = []

    for i, entry in enumerate(tickers):
        ticker_str = entry["ticker"]

        # Use cached entry if fresh enough — refresh universe metadata
        if ticker_str in cache:
            cached = {
                **cache[ticker_str],
                "sector":       entry.get("sector"),
                "sector_rank":  entry.get("sector_rank"),
                "sub_industry": entry.get("sub_industry"),
                "why_included": entry.get("why_included"),
                "verified_m3a": entry.get("verified"),
            }
            print(f"[{i+1}/{len(tickers)}] {ticker_str} — cached ({cached.get('fetched_at','?')[:10]}), skipping")
            results.append(cached)
            continue

        print(f"[{i+1}/{len(tickers)}] Fetching {ticker_str}...")

        try:
            technicals   = fetch_technicals(ticker_str)
            fundamentals = fetch_fundamentals(ticker_str)

            if technicals is None:
                print(f"  SKIP: insufficient price history for {ticker_str}")
                failed.append({"ticker": ticker_str, "reason": "insufficient_price_history"})
                time.sleep(RATE_LIMIT_SECONDS)
                continue

            derived    = compute_derived(fundamentals, technicals)
            validation = validate_filters(fundamentals, technicals)

            results.append({
                "fetched_at":    datetime.now(timezone.utc).isoformat(),
                "ticker":        ticker_str,
                "company_name":  fundamentals.get("company_name"),
                "sector":        entry.get("sector"),
                "sector_rank":   entry.get("sector_rank"),
                "sub_industry":  entry.get("sub_industry"),
                "why_included":  entry.get("why_included"),
                "verified_m3a":  entry.get("verified"),
                "filter_passed": validation["passed"],
                "filter_flags":  validation["flags"],
                "technicals":    technicals,
                "fundamentals":  fundamentals,
                "derived":       derived,
            })

        except Exception as exc:
            print(f"  ERROR: {ticker_str} — {exc}")
            failed.append({"ticker": ticker_str, "reason": str(exc)})

        time.sleep(RATE_LIMIT_SECONDS)

    return results, failed


# ---------------------------------------------------------------------------
# Output + summary
# ---------------------------------------------------------------------------

def build_output(results: list, failed: list, universe_meta: dict, output_path: Path) -> None:
    passed  = [r for r in results if r["filter_passed"]]
    flagged = [r for r in results if not r["filter_passed"]]

    total_attempted = len(results) + len(failed)
    if total_attempted > 0 and len(failed) / total_attempted > 0.30:
        print("WARNING: high failure rate — check yfinance connectivity or ticker validity.")

    output = {
        "generated_at":   universe_meta.get("cycle_date"),
        "source_file":    "M3A Universe generation/universe-generation.json",
        "rotation_score": universe_meta.get("rotation_score"),
        "cycle_phase":    universe_meta.get("cycle_phase"),
        "total_fetched":  len(results),
        "total_passed":   len(passed),
        "total_flagged":  len(flagged),
        "total_failed":   len(failed),
        "stocks":         passed,
        "flagged_stocks": flagged,
        "fetch_failures": failed,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    cycle_date = universe_meta.get("cycle_date") or str(date.today())
    print(f"\nFetch complete — {cycle_date}")
    print(f"Total tickers attempted : {total_attempted}")
    print(f"Passed all filters      : {len(passed)}")
    print(f"Flagged (review needed) : {len(flagged)}")
    print(f"Failed (no data)        : {len(failed)}")

    sector_counts: dict[str, int] = defaultdict(int)
    for r in passed:
        sector_counts[r.get("sector") or "Unknown"] += 1
    if sector_counts:
        print("\nSector distribution (passed):")
        for sector, count in sorted(sector_counts.items(), key=lambda x: -x[1]):
            print(f"  {sector:<28}: {count} stocks")

    # Top-3 null fields
    null_counts: dict[str, int] = defaultdict(int)
    if passed:
        all_keys: set[str] = set()
        for r in passed:
            all_keys.update(r.get("fundamentals", {}).keys())
            all_keys.update(r.get("derived", {}).keys())
        for key in all_keys:
            for r in passed:
                val = r.get("fundamentals", {}).get(key)
                if val is None:
                    val = r.get("derived", {}).get(key)
                if val is None:
                    null_counts[key] += 1
        top_nulls = sorted(null_counts.items(), key=lambda x: -x[1])[:3]
        if top_nulls:
            print("\nFields with highest null rate:")
            for field, count in top_nulls:
                print(f"  {field}: {count}/{len(passed)} null")

    print(f"\nOutput: {output_path}")


# ---------------------------------------------------------------------------
# Universe loader
# ---------------------------------------------------------------------------

def load_universe(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "universe" not in data:
        raise RunnerError(f"{path} is missing a 'universe' key.")
    return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch yfinance data for each ticker in universe-generation.json "
                    "and write universe-generation-api.json."
    )
    parser.add_argument(
        "--input-file", default=str(INPUT_PATH),
        help="Path to universe-generation.json.",
    )
    parser.add_argument(
        "--tickers", nargs="+", metavar="TICKER",
        help="Override: fetch only these tickers (for testing).",
    )
    parser.add_argument(
        "--output", default=str(OUTPUT_PATH),
        help="Output path for universe-generation-api.json.",
    )
    return parser.parse_args()


def main() -> None:
    load_env_file(ENV_PATH)
    args = parse_args()
    output_path = Path(args.output)

    if args.tickers:
        tickers       = [{"ticker": t.upper()} for t in args.tickers]
        universe_meta = {"cycle_date": str(date.today()), "rotation_score": None, "cycle_phase": None}
    else:
        input_path = Path(args.input_file)
        if not input_path.exists():
            raise RunnerError(f"Input file not found: {input_path}")
        universe      = load_universe(input_path)
        tickers       = universe["universe"]
        universe_meta = {
            "cycle_date":     universe.get("cycle_date"),
            "rotation_score": universe.get("rotation_score"),
            "cycle_phase":    universe.get("cycle_phase"),
        }

    cache = load_cache(output_path)
    if cache:
        print(f"Cache: {len(cache)} ticker(s) fresh (< {CACHE_TTL_DAYS}d), will skip those")

    print(f"Fetching yfinance data for {len(tickers)} ticker(s)...")
    results, failed = fetch_all(tickers, cache)
    build_output(results, failed, universe_meta, output_path)


if __name__ == "__main__":
    main()
