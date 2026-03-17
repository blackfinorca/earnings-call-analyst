#!/usr/bin/env python3
"""Fetch financial data from FMP for each ticker in the universe JSON."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, timedelta
from json import JSONDecodeError
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"
DEFAULT_INPUT_PATH = Path(__file__).with_name("universe-generation.json")
DEFAULT_OUTPUT_PATH = Path(__file__).with_name("universe-generation-api.json")

FMP_API_ENV_VAR = "FMP_API_KEY"
FMP_BASE_URL = "https://financialmodelingprep.com/stable"
DEFAULT_TIMEOUT_SECONDS = 30
HISTORY_MONTHS = 13


# ---------------------------------------------------------------------------
# Env / config helpers
# ---------------------------------------------------------------------------

class FmpRunnerError(RuntimeError):
    """Raised for fatal errors in the FMP runner."""


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


def resolve_api_key(explicit: str | None) -> str:
    if explicit:
        return explicit
    key = os.getenv(FMP_API_ENV_VAR)
    if key:
        return key
    raise FmpRunnerError(
        f"Missing {FMP_API_ENV_VAR}. Set it in .env or export it in the shell."
    )


# ---------------------------------------------------------------------------
# FMP HTTP helper
# ---------------------------------------------------------------------------

def fmp_get(
    endpoint: str,
    params: dict[str, str],
    api_key: str,
    timeout: int,
) -> Any:
    """GET a FMP stable endpoint and return the parsed JSON body (or None on 404)."""
    params = {**params, "apikey": api_key}
    url = f"{FMP_BASE_URL}{endpoint}?{urlencode(params)}"
    try:
        with urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return None
        payload = exc.read().decode("utf-8", errors="replace").strip()
        raise FmpRunnerError(f"FMP HTTP {exc.code} for {endpoint}: {payload[:300]}") from exc
    except URLError as exc:
        raise FmpRunnerError(f"FMP network error for {endpoint}: {exc}") from exc
    except JSONDecodeError as exc:
        raise FmpRunnerError(f"FMP returned non-JSON for {endpoint}.") from exc


def safe_list(value: Any, limit: int | None = None) -> list:
    if not isinstance(value, list):
        return []
    return value[:limit] if limit else value


def safe_first(value: Any) -> dict:
    lst = safe_list(value)
    return lst[0] if lst else {}


def ratio(numerator: Any, denominator: Any) -> float | None:
    """Compute numerator/denominator; return None if either is falsy."""
    try:
        if numerator is None or denominator is None or denominator == 0:
            return None
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return None


# ---------------------------------------------------------------------------
# Per-field fetchers
# ---------------------------------------------------------------------------

def fetch_price_and_market_data(symbol: str, api_key: str, timeout: int) -> dict:
    # /stable/quote  — symbol as query param, returns list
    quote = safe_first(fmp_get("/quote", {"symbol": symbol}, api_key, timeout))
    # /stable/profile — richer metadata (beta, averageVolume, description, etc.)
    profile = safe_first(fmp_get("/profile", {"symbol": symbol}, api_key, timeout))
    return {
        "symbol": quote.get("symbol"),
        "name": profile.get("companyName"),
        "price": quote.get("price"),
        "change_pct": quote.get("changePercentage"),
        "market_cap": quote.get("marketCap"),
        "avg_volume": profile.get("averageVolume"),
        "52w_high": quote.get("yearHigh"),
        "52w_low": quote.get("yearLow"),
        "beta": profile.get("beta"),
        "sector": profile.get("sector"),
        "industry": profile.get("industry"),
        "exchange": profile.get("exchange"),
        "currency": profile.get("currency"),
        "country": profile.get("country"),
        "description": profile.get("description"),
    }


def fetch_valuation_multiples(symbol: str, api_key: str, timeout: int) -> dict:
    # /stable/ratios-ttm — TTM price/valuation ratios
    ttm = safe_first(fmp_get("/ratios-ttm", {"symbol": symbol}, api_key, timeout))
    # /stable/key-metrics-ttm — EV multiples, ROE, ROA
    km = safe_first(fmp_get("/key-metrics-ttm", {"symbol": symbol}, api_key, timeout))
    return {
        "pe_ttm": ttm.get("priceToEarningsRatioTTM"),
        "pb_ttm": ttm.get("priceToBookRatioTTM"),
        "ps_ttm": ttm.get("priceToSalesRatioTTM"),
        "pfcf_ttm": ttm.get("priceToFreeCashFlowRatioTTM"),
        "ev_ebitda_ttm": km.get("evToEBITDATTM"),
        "ev_sales_ttm": km.get("evToSalesTTM"),
        "ev_fcf_ttm": km.get("evToFreeCashFlowTTM"),
        "ev_ocf_ttm": km.get("evToOperatingCashFlowTTM"),
        "roe_ttm": km.get("returnOnEquityTTM"),
        "roa_ttm": km.get("returnOnAssetsTTM"),
        "debt_equity_ttm": ttm.get("debtToEquityRatioTTM"),
        "current_ratio_ttm": ttm.get("currentRatioTTM"),
        "gross_margin_ttm": ttm.get("grossProfitMarginTTM"),
        "ebitda_margin_ttm": ttm.get("ebitdaMarginTTM"),
        "operating_margin_ttm": ttm.get("operatingProfitMarginTTM"),
        "net_margin_ttm": ttm.get("netProfitMarginTTM"),
        "dividend_yield_ttm": ttm.get("dividendYieldTTM"),
        "payout_ratio_ttm": ttm.get("dividendPayoutRatioTTM"),
    }


def fetch_income_statement(symbol: str, api_key: str, timeout: int) -> list:
    data = safe_list(
        fmp_get(
            "/income-statement",
            {"symbol": symbol, "period": "annual", "limit": "4"},
            api_key,
            timeout,
        ),
        limit=4,
    )
    return [
        {
            "date": r.get("date"),
            "fiscal_year": r.get("fiscalYear"),
            "period": r.get("period"),
            "reported_currency": r.get("reportedCurrency"),
            "revenue": r.get("revenue"),
            "gross_profit": r.get("grossProfit"),
            "gross_margin": ratio(r.get("grossProfit"), r.get("revenue")),
            "operating_income": r.get("operatingIncome"),
            "operating_margin": ratio(r.get("operatingIncome"), r.get("revenue")),
            "ebitda": r.get("ebitda"),
            "ebitda_margin": ratio(r.get("ebitda"), r.get("revenue")),
            "net_income": r.get("netIncome"),
            "net_margin": ratio(r.get("netIncome"), r.get("revenue")),
            "eps_diluted": r.get("epsDiluted"),
            "eps_basic": r.get("eps"),
            "shares_diluted": r.get("weightedAverageShsOutDil"),
            "rd_expense": r.get("researchAndDevelopmentExpenses"),
        }
        for r in data
    ]


def fetch_balance_sheet(symbol: str, api_key: str, timeout: int) -> list:
    data = safe_list(
        fmp_get(
            "/balance-sheet-statement",
            {"symbol": symbol, "period": "annual", "limit": "4"},
            api_key,
            timeout,
        ),
        limit=4,
    )
    return [
        {
            "date": r.get("date"),
            "fiscal_year": r.get("fiscalYear"),
            "period": r.get("period"),
            "cash_and_equivalents": r.get("cashAndCashEquivalents"),
            "short_term_investments": r.get("shortTermInvestments"),
            "total_current_assets": r.get("totalCurrentAssets"),
            "total_assets": r.get("totalAssets"),
            "total_current_liabilities": r.get("totalCurrentLiabilities"),
            "short_term_debt": r.get("shortTermDebt"),
            "long_term_debt": r.get("longTermDebt"),
            "total_debt": r.get("totalDebt"),
            "net_debt": r.get("netDebt"),
            "total_liabilities": r.get("totalLiabilities"),
            "total_equity": r.get("totalStockholdersEquity"),
            "retained_earnings": r.get("retainedEarnings"),
            "goodwill": r.get("goodwill"),
            "intangible_assets": r.get("intangibleAssets"),
        }
        for r in data
    ]


def fetch_cash_flow(symbol: str, api_key: str, timeout: int) -> list:
    data = safe_list(
        fmp_get(
            "/cash-flow-statement",
            {"symbol": symbol, "period": "annual", "limit": "4"},
            api_key,
            timeout,
        ),
        limit=4,
    )
    return [
        {
            "date": r.get("date"),
            "fiscal_year": r.get("fiscalYear"),
            "period": r.get("period"),
            "operating_cash_flow": r.get("operatingCashFlow"),
            "capex": r.get("capitalExpenditure"),
            "free_cash_flow": r.get("freeCashFlow"),
            "dividends_paid": r.get("commonDividendsPaid"),
            "share_buybacks": r.get("commonStockRepurchased"),
            "net_change_in_cash": r.get("netChangeInCash"),
            "depreciation_amortization": r.get("depreciationAndAmortization"),
            "stock_based_compensation": r.get("stockBasedCompensation"),
        }
        for r in data
    ]


def fetch_analyst_data(symbol: str, api_key: str, timeout: int) -> dict:
    # /stable/grades — most recent individual grade actions (no summary endpoint available)
    grades = safe_list(fmp_get("/grades", {"symbol": symbol}, api_key, timeout), limit=10)
    # /stable/price-target-consensus — high/low/mean/median targets
    pt = safe_first(fmp_get("/price-target-consensus", {"symbol": symbol}, api_key, timeout))
    return {
        "price_target_high": pt.get("targetHigh"),
        "price_target_low": pt.get("targetLow"),
        "price_target_consensus": pt.get("targetConsensus"),
        "price_target_median": pt.get("targetMedian"),
        "recent_grades": [
            {
                "date": g.get("date"),
                "analyst_firm": g.get("gradingCompany"),
                "action": g.get("action"),
                "previous_grade": g.get("previousGrade"),
                "new_grade": g.get("newGrade"),
            }
            for g in grades
        ],
    }


def fetch_historical_prices(symbol: str, api_key: str, timeout: int) -> list:
    today = date.today()
    from_date = (today - timedelta(days=HISTORY_MONTHS * 31)).isoformat()
    to_date = today.isoformat()
    result = fmp_get(
        "/historical-price-eod/full",
        {"symbol": symbol, "from": from_date, "to": to_date},
        api_key,
        timeout,
    )
    # stable endpoint returns a list directly
    rows = result if isinstance(result, list) else (
        result.get("historical", []) if isinstance(result, dict) else []
    )
    return [
        {
            "date": r.get("date"),
            "open": r.get("open"),
            "high": r.get("high"),
            "low": r.get("low"),
            "close": r.get("close"),
            "adj_close": r.get("adjClose"),
            "volume": r.get("volume"),
            "change_pct": r.get("changePercent"),
        }
        for r in safe_list(rows)
    ]


def fetch_key_metrics(symbol: str, api_key: str, timeout: int) -> dict:
    # /stable/key-metrics-ttm — ROIC and other TTM metrics
    ttm = safe_first(fmp_get("/key-metrics-ttm", {"symbol": symbol}, api_key, timeout))
    # /stable/key-metrics?period=annual&limit=1 — most recent annual snapshot
    annual = safe_first(
        fmp_get(
            "/key-metrics",
            {"symbol": symbol, "period": "annual", "limit": "1"},
            api_key,
            timeout,
        )
    )
    return {
        "roic_ttm": ttm.get("returnOnInvestedCapitalTTM"),
        "roic_annual": annual.get("returnOnInvestedCapital"),
        "roce_ttm": ttm.get("returnOnCapitalEmployedTTM"),
        "roe_ttm": ttm.get("returnOnEquityTTM"),
        "roa_ttm": ttm.get("returnOnAssetsTTM"),
        "fcf_yield_ttm": ttm.get("freeCashFlowYieldTTM"),
        "earnings_yield_ttm": ttm.get("earningsYieldTTM"),
        "ev_ebitda_ttm": ttm.get("evToEBITDATTM"),
        "ev_to_ocf_ttm": ttm.get("evToOperatingCashFlowTTM"),
        "ev_to_fcf_ttm": ttm.get("evToFreeCashFlowTTM"),
        "net_debt_to_ebitda_ttm": ttm.get("netDebtToEBITDATTM"),
        "invested_capital": annual.get("investedCapital"),
        "tangible_asset_value": annual.get("tangibleAssetValue"),
        "net_current_asset_value": annual.get("netCurrentAssetValue"),
        "capex_to_revenue_ttm": ttm.get("capexToRevenueTTM"),
        "sbc_to_revenue_ttm": ttm.get("stockBasedCompensationToRevenueTTM"),
    }


def fetch_forward_estimates(symbol: str, api_key: str, timeout: int) -> list:
    data = safe_list(
        fmp_get(
            "/analyst-estimates",
            {"symbol": symbol, "period": "annual", "limit": "4"},
            api_key,
            timeout,
        ),
        limit=4,
    )
    return [
        {
            "date": r.get("date"),
            "estimated_revenue_low": r.get("revenueLow"),
            "estimated_revenue_high": r.get("revenueHigh"),
            "estimated_revenue_avg": r.get("revenueAvg"),
            "estimated_ebitda_avg": r.get("ebitdaAvg"),
            "estimated_ebit_avg": r.get("ebitAvg"),
            "estimated_net_income_avg": r.get("netIncomeAvg"),
            "estimated_eps_avg": r.get("epsAvg"),
            "estimated_eps_low": r.get("epsLow"),
            "estimated_eps_high": r.get("epsHigh"),
        }
        for r in data
    ]


# ---------------------------------------------------------------------------
# Per-ticker orchestrator
# ---------------------------------------------------------------------------

def fetch_ticker(symbol: str, api_key: str, timeout: int, verbose: bool) -> dict:
    steps = [
        ("price_and_market_data", fetch_price_and_market_data),
        ("valuation_multiples", fetch_valuation_multiples),
        ("income_statement", fetch_income_statement),
        ("balance_sheet", fetch_balance_sheet),
        ("cash_flow", fetch_cash_flow),
        ("analyst_data", fetch_analyst_data),
        ("historical_prices", fetch_historical_prices),
        ("key_metrics", fetch_key_metrics),
        ("forward_estimates", fetch_forward_estimates),
    ]
    result: dict[str, Any] = {}
    for field_name, fetcher in steps:
        if verbose:
            print(f"  [{symbol}] fetching {field_name}...")
        try:
            result[field_name] = fetcher(symbol, api_key, timeout)
        except FmpRunnerError as exc:
            print(f"  [{symbol}] WARNING – {field_name} failed: {exc}")
            result[field_name] = None
    return result


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def load_tickers(input_path: Path | None, tickers_arg: list[str] | None) -> list[str]:
    """Return ticker list from CLI override, input JSON, or raise."""
    if tickers_arg:
        return [t.strip().upper() for t in tickers_arg]
    if input_path and input_path.exists():
        raw = json.loads(input_path.read_text(encoding="utf-8"))
        # Accept: list of strings, list of dicts with "ticker"/"symbol", or top-level dict keys
        if isinstance(raw, list):
            if all(isinstance(x, str) for x in raw):
                return [t.upper() for t in raw]
            if all(isinstance(x, dict) for x in raw):
                for key in ("ticker", "symbol", "Ticker", "Symbol"):
                    if key in raw[0]:
                        return [x[key].upper() for x in raw if key in x]
        if isinstance(raw, dict):
            for key in ("tickers", "universe", "symbols"):
                if key in raw and isinstance(raw[key], list):
                    return [t.upper() for t in raw[key]]
            # fallback: top-level keys are ticker symbols
            return [k.upper() for k in raw.keys()]
    raise FmpRunnerError(
        "No tickers found. Provide --tickers or a valid --input-file."
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch FMP financial data for each ticker in the universe JSON."
    )
    parser.add_argument(
        "--input-file",
        default=str(DEFAULT_INPUT_PATH),
        help="Path to universe-generation.json (the ticker universe).",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        metavar="TICKER",
        help="Override: fetch data for these tickers instead of reading the input file.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Where to write universe-generation-api.json.",
    )
    parser.add_argument(
        "--api-key",
        help=f"Override {FMP_API_ENV_VAR} from the environment.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="HTTP timeout per FMP request (seconds).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print progress for each ticker and field.",
    )
    return parser.parse_args()


def main() -> None:
    load_env_file(ENV_PATH)
    args = parse_args()

    api_key = resolve_api_key(args.api_key)
    input_path = Path(args.input_file)
    output_path = Path(args.output)

    tickers = load_tickers(input_path, args.tickers)
    print(f"Fetching FMP data for {len(tickers)} ticker(s): {', '.join(tickers)}")

    output: dict[str, Any] = {}
    for symbol in tickers:
        print(f"→ {symbol}")
        output[symbol] = fetch_ticker(symbol, api_key, args.timeout_seconds, args.verbose)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"\nSaved → {output_path}")


if __name__ == "__main__":
    main()
