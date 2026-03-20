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

import math
import random
import re

import yfinance as yf

try:
    import anthropic as _anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


BASE_DIR   = Path(__file__).resolve().parent
ENV_PATH   = BASE_DIR.parent / ".env"
INPUT_PATH = BASE_DIR / "universe-generation.json"
OUTPUT_PATH = BASE_DIR / "universe-generation-api.json"

CACHE_TTL_DAYS     = 0   # 0 = always fetch fresh data on every run
RATE_LIMIT_SECONDS = 0.3   # yfinance / Yahoo rate limit buffer
RETRY_DELAY        = 2.0   # seconds to wait before a single retry

ANTHROPIC_MODEL      = "claude-sonnet-4-6"
HAIKU_MODEL          = "claude-haiku-4-5-20251001"  # fast model for enrichment

# Fields added in this version — cached entries missing these will be re-fetched
_CACHE_SENTINEL_FIELDS = {"shares_outstanding", "stock_based_compensation"}


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


def _is_nan(val) -> bool:
    """Return True for float NaN, None, or pandas NA."""
    if val is None:
        return True
    try:
        return math.isnan(float(val))
    except (TypeError, ValueError):
        return False


def _stmt_row(df, *labels: str) -> float | None:
    """Return the most-recent annual value for the first matching row label in a DataFrame."""
    if df is None or df.empty:
        return None
    for label in labels:
        if label in df.index:
            val = df.loc[label].iloc[0]
            return None if _is_nan(val) else float(val)
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
        "peg_ratio":               sv(info, "pegRatio") or sv(info, "trailingPegRatio"),
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
        "institutional_ownership": (
            pct_val(info, "heldPercentInstitutions")
            or pct_val(info, "institutionsPercentHeld")
        ),
        "insider_ownership":       (
            pct_val(info, "heldPercentInsiders")
            or pct_val(info, "insidersPercentHeld")
        ),

        # Analyst breadth
        "analyst_count":           sv(info, "numberOfAnalystOpinions"),

        # Share count (for dilution tracking, Cat 3)
        "shares_outstanding":      sv(info, "sharesOutstanding"),
    }


# ---------------------------------------------------------------------------
# Supplemental yfinance data — financial statements + analyst ratings
# ---------------------------------------------------------------------------

def fetch_statements(symbol: str) -> dict:
    """
    Fetch line items from annual income statement, balance sheet, and cash flow
    that are needed for M5 scoring (ROIC, interest coverage, capital allocation).
    Returns a dict of fields to merge into fundamentals.
    """
    result: dict = {
        "operating_income":         None,
        "interest_expense":         None,
        "total_stockholder_equity": None,
        "stock_based_compensation": None,
        "tax_provision":            None,
        "pretax_income":            None,
    }
    tk = yf.Ticker(symbol)

    # Income statement — operating income, interest expense, tax rate inputs
    try:
        stmt = tk.income_stmt
        result["operating_income"]  = _stmt_row(stmt, "Operating Income", "EBIT")
        ie = _stmt_row(stmt, "Interest Expense", "Interest Expense Non Operating")
        result["interest_expense"]  = abs(ie) if ie is not None else None
        result["tax_provision"]     = _stmt_row(stmt, "Tax Provision", "Income Tax Expense")
        result["pretax_income"]     = _stmt_row(stmt, "Pretax Income", "Income Before Tax")
    except Exception:
        pass

    # Balance sheet — stockholder equity
    try:
        bs = tk.balance_sheet
        result["total_stockholder_equity"] = _stmt_row(
            bs,
            "Stockholders Equity",
            "Total Stockholder Equity",
            "Common Stock Equity",
            "Total Equity Gross Minority Interest",
        )
    except Exception:
        pass

    # Cash flow — stock-based compensation
    try:
        cf = tk.cashflow
        sbc = _stmt_row(cf, "Stock Based Compensation", "Share Based Compensation Expense")
        result["stock_based_compensation"] = abs(sbc) if sbc is not None else None
    except Exception:
        pass

    return result


def fetch_recommendations(symbol: str) -> dict:
    """
    Fetch analyst buy/hold/sell breakdown from yfinance recommendations_summary.
    Returns a dict with analyst_buy_count, analyst_hold_count, analyst_sell_count.
    """
    result: dict = {
        "analyst_buy_count":  None,
        "analyst_hold_count": None,
        "analyst_sell_count": None,
    }
    try:
        tk      = yf.Ticker(symbol)
        summary = tk.recommendations_summary
        if summary is None or summary.empty:
            return result
        row = summary.iloc[0]
        def _int(val) -> int:
            return int(val) if val is not None and not _is_nan(val) else 0
        result["analyst_buy_count"]  = _int(row.get("strongBuy")) + _int(row.get("buy"))
        result["analyst_hold_count"] = _int(row.get("hold"))
        result["analyst_sell_count"] = _int(row.get("sell")) + _int(row.get("strongSell"))
    except Exception:
        pass
    return result


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

    # Interest coverage ratio = operating_income / interest_expense  (Cat 2)
    op_inc  = fundamentals.get("operating_income")
    int_exp = fundamentals.get("interest_expense")
    derived["interest_coverage"] = (
        round(op_inc / int_exp, 2)
        if op_inc is not None and int_exp and int_exp > 0
        else None
    )

    # ROIC approximation = NOPAT / invested_capital  (Cat 3)
    equity  = fundamentals.get("total_stockholder_equity")
    tax_p   = fundamentals.get("tax_provision")
    pre_tax = fundamentals.get("pretax_income")
    debt    = fundamentals.get("total_debt") or 0
    cash    = fundamentals.get("cash_and_equivalents") or 0
    if op_inc is not None and equity is not None:
        tax_rate   = (tax_p / pre_tax) if tax_p and pre_tax and pre_tax != 0 else 0.21
        nopat      = op_inc * (1 - min(max(tax_rate, 0), 0.5))
        inv_cap    = debt + equity - cash
        derived["roic_approx"] = round(nopat / inv_cap * 100, 2) if inv_cap and inv_cap != 0 else None
    else:
        derived["roic_approx"] = None

    # SBC as % of revenue  (Cat 3)
    sbc = fundamentals.get("stock_based_compensation")
    rev = fundamentals.get("revenue_ttm")
    derived["sbc_pct_of_revenue"] = (
        round(sbc / rev * 100, 2) if sbc and rev and rev > 0 else None
    )

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
            if fetched_at <= cutoff:
                continue
        except ValueError:
            continue
        # Invalidate entries that predate the new statement-derived fields
        fund = entry.get("fundamentals", {})
        if not all(f in fund for f in _CACHE_SENTINEL_FIELDS):
            continue
        cache[entry["ticker"]] = entry
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

            # Merge statement-derived fields and analyst breakdown into fundamentals
            fundamentals.update(fetch_statements(ticker_str))
            fundamentals.update(fetch_recommendations(ticker_str))

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
# Haiku enrichment — fill null peg_ratio / institutional_ownership via a
# single fast Haiku call (knowledge-only, no web search tool)
# ---------------------------------------------------------------------------

def _resolve_api_key() -> str | None:
    return os.getenv("ANTHROPIC_API_KEY")


def _parse_enrich_json(text: str) -> dict | None:
    """Extract the first valid JSON object from a response string."""
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text, m.start())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def enrich_with_haiku(client, stocks: list[dict]) -> None:
    """
    Single Haiku call (no web search) to fill null peg_ratio and
    institutional_ownership for stocks where yfinance returned None.
    Uses Haiku's training-data knowledge — fast, no tool calls.
    """
    _ENRICH_FIELDS = ("peg_ratio", "institutional_ownership")
    needs = [
        s for s in stocks
        if any(s.get("fundamentals", {}).get(f) is None for f in _ENRICH_FIELDS)
    ]
    if not needs:
        print("[enrich] All peg_ratio / institutional_ownership values present — skipping.", flush=True)
        return

    ticker_list = [
        {"ticker": s["ticker"], "name": s.get("company_name", s["ticker"])}
        for s in needs
    ]
    print(f"[enrich] {len(needs)} stock(s) have null fields — asking Haiku to fill...", flush=True)

    system = (
        "You are a financial data assistant. Return ONLY a raw JSON object with no "
        "markdown, no code fences, and no commentary. Use null for any value you are "
        "uncertain about."
    )
    user_msg = (
        "For each ticker below, provide your best estimate of:\n"
        "  peg_ratio — trailing or forward PEG ratio (float, or null)\n"
        "  institutional_ownership_pct — % of shares held by institutions (0-100, or null)\n\n"
        f"Tickers: {json.dumps(ticker_list)}\n\n"
        'Return exactly: {"TICKER": {"peg_ratio": number_or_null, '
        '"institutional_ownership_pct": number_or_null}, ...}'
    )

    _MAX_RETRIES = 3
    _BASE_DELAY  = 2.0
    _MAX_DELAY   = 30.0

    response = None
    last_exc  = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = client.messages.create(
                model=HAIKU_MODEL,
                system=system,
                max_tokens=2000,
                temperature=0.0,
                messages=[{"role": "user", "content": user_msg}],
            )
            break
        except _anthropic.RateLimitError as exc:
            last_exc = exc
            delay = min(_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1), _MAX_DELAY)
        except _anthropic.APIStatusError as exc:
            if exc.status_code < 500:
                raise
            last_exc = exc
            delay = min(_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1), _MAX_DELAY)
        except _anthropic.APIConnectionError as exc:
            last_exc = exc
            delay = min(_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1), _MAX_DELAY)
        print(f"  [enrich] Retry {attempt + 1}/{_MAX_RETRIES} — waiting {delay:.1f}s...", flush=True)
        time.sleep(delay)

    if response is None:
        print(f"  [enrich] Failed after {_MAX_RETRIES} retries: {last_exc}", flush=True)
        return

    text = " ".join(
        b.text for b in response.content
        if hasattr(b, "type") and b.type == "text" and b.text
    )
    enriched = _parse_enrich_json(text)
    if not enriched:
        print("  [enrich] Could not parse Haiku response — skipping enrichment.", flush=True)
        return

    filled_count = 0
    for stock in needs:
        ticker = stock["ticker"]
        data   = enriched.get(ticker, {})
        if not data:
            continue
        fund = stock.setdefault("fundamentals", {})
        filled: list[str] = []
        if data.get("peg_ratio") is not None and fund.get("peg_ratio") is None:
            fund["peg_ratio"] = data["peg_ratio"]
            filled.append("peg_ratio")
        if data.get("institutional_ownership_pct") is not None and fund.get("institutional_ownership") is None:
            fund["institutional_ownership"] = data["institutional_ownership_pct"]
            filled.append("institutional_ownership")
        if filled:
            filled_count += 1
            print(f"  [enrich] {ticker}: filled {filled}", flush=True)

    print(f"[enrich] Done — enriched {filled_count}/{len(needs)} stock(s).", flush=True)


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

    # Haiku enrichment — fast single call to fill null peg_ratio / institutional_ownership
    if _ANTHROPIC_AVAILABLE:
        api_key = _resolve_api_key()
        if api_key:
            client = _anthropic.Anthropic(api_key=api_key)
            enrich_with_haiku(client, results)
        else:
            print("[enrich] ANTHROPIC_API_KEY not set — skipping enrichment.", flush=True)
    else:
        print("[enrich] anthropic package not installed — skipping enrichment.", flush=True)

    build_output(results, failed, universe_meta, output_path)


if __name__ == "__main__":
    main()
