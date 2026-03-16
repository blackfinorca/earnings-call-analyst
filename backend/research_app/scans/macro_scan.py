#!/usr/bin/env python3
"""Macro scan backend for the investment strategy research app."""

from __future__ import annotations

import argparse
import html as html_lib
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote as urlquote, urlencode
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parents[3]
PHASE_DIR = BASE_DIR / "M1 macro scan"
DATA_DIR = BASE_DIR / "data"
STATE_DIR = DATA_DIR / "state"
ENV_PATH = BASE_DIR / ".env"

FMP_API_ENV_VAR = "FMP_API_KEY"
FMP_BASE_URL = "https://financialmodelingprep.com/stable"
YAHOO_CHART_BASE_URL = "https://query2.finance.yahoo.com/v8/finance/chart"
TRADING_ECONOMICS_BASE_URL = "https://tradingeconomics.com"
DEFAULT_OUTPUT_PATH = PHASE_DIR / "research-macro-scan.json"
STATE_PATH = STATE_DIR / "fmp-state.json"
SECONDARY_STATE_PATH = STATE_DIR / "yahoo-state.json"
TRADING_ECONOMICS_STATE_PATH = STATE_DIR / "tradingeconomics-state.json"
DEFAULT_DAILY_LIMIT = 249


class FmpApiError(RuntimeError):
    """Base error for FMP API failures."""


class FmpRestrictedError(FmpApiError):
    """Raised when a free-tier restricted endpoint or symbol is requested."""


class FmpInvalidNameError(FmpApiError):
    """Raised when an unsupported economic indicator name is requested."""


class YahooFinanceError(RuntimeError):
    """Raised when Yahoo Finance fallback data is unavailable."""


class TradingEconomicsError(RuntimeError):
    """Raised when Trading Economics fallback data is unavailable."""


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


def resolve_fmp_api_key(explicit_api_key: str | None = None) -> str:
    if explicit_api_key:
        return explicit_api_key

    api_key = os.getenv(FMP_API_ENV_VAR)
    if api_key:
        return api_key

    raise RuntimeError(
        "Missing FMP_API_KEY. Set it in the project .env file or export it in the shell."
    )


load_env_file(ENV_PATH)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def format_number(value: float | int | None, digits: int = 2) -> str | None:
    if value is None:
        return None
    formatted = f"{value:,.{digits}f}"
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted


def format_percent(value: float | None, digits: int = 2) -> str | None:
    if value is None:
        return None
    return f"{value:.{digits}f}%"


def format_signed_percent(value: float | None, digits: int = 2) -> str | None:
    if value is None:
        return None
    return f"{value:+.{digits}f}%"


def format_rate_range(lower: float | None, upper: float | None, digits: int = 2) -> str | None:
    if lower is None or upper is None:
        return None
    return f"{lower:.{digits}f}-{upper:.{digits}f}%"


def format_currency(
    value: float | None,
    digits: int = 2,
    suffix: str = "",
) -> str | None:
    if value is None:
        return None
    return f"${value:,.{digits}f}{suffix}"


def format_thousands(value: float | int | None) -> str | None:
    if value is None:
        return None
    return f"{round(float(value) / 1_000):,.0f}K"


def numeric_direction(
    current: float | None,
    prior: float | None,
    tolerance: float = 1e-9,
) -> str | None:
    if current is None or prior is None:
        return None
    if abs(current - prior) <= tolerance:
        return "flat"
    return "up" if current > prior else "down"


def range_direction(
    current_lower: float | None,
    current_upper: float | None,
    prior_lower: float | None,
    prior_upper: float | None,
) -> str | None:
    if None in (current_lower, current_upper, prior_lower, prior_upper):
        return None
    if current_lower == prior_lower and current_upper == prior_upper:
        return "flat"
    if current_lower > prior_lower or current_upper > prior_upper:
        return "up"
    return "down"


def pct_change(current: float | None, prior: float | None) -> float | None:
    if current is None or prior in (None, 0):
        return None
    return ((current / prior) - 1.0) * 100.0


def start_of_same_month_last_year(value: date) -> date:
    return date(value.year - 1, value.month, 1)


def annualized_quarterly_growth(current: float, prior: float) -> float:
    return ((current / prior) ** 4 - 1.0) * 100.0


def build_source(path: str, params: dict[str, Any]) -> dict[str, str]:
    query = urlencode(params)
    url = f"{FMP_BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"
    return {
        "provider": "Financial Modeling Prep",
        "path": path,
        "url": url,
    }


def quarter_label(value: date) -> str:
    quarter = ((value.month - 1) // 3) + 1
    return f"Q{quarter} {value.year}"


MONTH_NUMBERS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


ROW_ORDER = [
    "S&P 500",
    "Nasdaq",
    "Russell 2000",
    "VIX",
    "Fed Funds Rate",
    "10Y Treasury Yield",
    "2Y Treasury Yield",
    "10Y-2Y Spread",
    "CPI YoY",
    "Core PCE YoY",
    "ISM Manufacturing PMI",
    "ISM Services PMI",
    "Unemployment Rate",
    "Initial Jobless Claims",
    "WTI Crude Oil",
    "Gold Price",
    "DXY Dollar Index",
    "US GDP",
]


def price_signal(label: str, current: float, prior: float) -> str:
    change = pct_change(current, prior)
    if change is None:
        return f"{label} reading captured."
    if change >= 0.75:
        tone = "Strong upside move"
    elif change >= 0.15:
        tone = "Positive day"
    elif change <= -0.75:
        tone = "Clear risk-off move"
    elif change <= -0.15:
        tone = "Soft session"
    else:
        tone = "Mostly flat"
    return f"{tone}; {change:+.2f}% versus the prior close."


def vix_signal(current: float, prior: float) -> str:
    change = pct_change(current, prior)
    if current >= 25:
        level_note = "Elevated volatility"
    elif current >= 20:
        level_note = "Volatility above normal"
    else:
        level_note = "Volatility still contained"
    if change is None:
        return level_note + "."
    return f"{level_note}; {change:+.2f}% versus the prior close."


def fed_signal(current_lower: float, current_upper: float, prior_lower: float, prior_upper: float) -> str:
    if current_lower == prior_lower and current_upper == prior_upper:
        return "Implied target range unchanged from the prior reading."
    if current_lower > prior_lower:
        return "Implied target range moved higher."
    return "Implied target range moved lower."


def treasury_signal(current: float, prior: float, tenor: str) -> str:
    change_bp = (current - prior) * 100.0
    if abs(change_bp) < 1:
        tone = "Stable"
    elif change_bp > 0:
        tone = "Higher"
    else:
        tone = "Lower"
    return f"{tone} versus one week earlier by {change_bp:+.0f} bps for the {tenor}."


def spread_signal(current: float) -> str:
    if current < 0:
        return "Yield curve inverted."
    if current < 0.5:
        return "Yield curve positive but still fairly narrow."
    return "Yield curve positive with a normal upward slope."


def inflation_signal(current: float) -> str:
    if current > 3.0:
        return "Inflation is still running well above the Fed's target."
    if current > 2.0:
        return "Inflation remains above the Fed's 2% target."
    return "Inflation is close to the Fed's 2% target."


def unemployment_signal(current: float) -> str:
    if current < 4.0:
        return "Labor market still looks tight."
    if current <= 4.5:
        return "Labor market is stable but softer than peak-tight conditions."
    return "Labor market is showing broader slack."


def claims_signal(current: float) -> str:
    if current < 225_000:
        return "Claims remain near cycle lows with limited layoff pressure."
    if current < 275_000:
        return "Claims are still normal, though not at cycle lows."
    return "Claims are rising enough to watch for labor-market stress."


def gold_signal(current: float, prior: float) -> str:
    change = pct_change(current, prior)
    if current >= 5_000:
        level_note = "Gold remains above $5,000 per ounce"
    elif current >= 4_500:
        level_note = "Gold is still elevated"
    else:
        level_note = "Gold is off extreme highs"
    if change is None:
        return level_note + "."
    return f"{level_note}; {change:+.2f}% versus the prior close."


def oil_signal(current: float, prior: float) -> str:
    change = pct_change(current, prior)
    if current >= 90:
        level_note = "Oil is elevated"
    elif current >= 80:
        level_note = "Oil is firm"
    else:
        level_note = "Oil is softer"
    if change is None:
        return level_note + "."
    return f"{level_note}; {change:+.2f}% versus the prior close."


def dollar_signal(current: float, prior: float) -> str:
    change = pct_change(current, prior)
    if change is None:
        return "Dollar index reading captured."
    if change > 0:
        return f"Dollar strengthening; {change:+.2f}% versus the prior close."
    if change < 0:
        return f"Dollar softening; {change:+.2f}% versus the prior close."
    return "Dollar index unchanged versus the prior close."


def core_pce_signal(current: float, prior: float) -> str:
    if current > prior:
        direction_note = "Fed's preferred inflation gauge moved higher."
    elif current < prior:
        direction_note = "Fed's preferred inflation gauge eased."
    else:
        direction_note = "Fed's preferred inflation gauge was unchanged."
    if current > 3.0:
        return f"{direction_note} It remains well above the Fed's target."
    if current > 2.0:
        return f"{direction_note} It remains above the Fed's target."
    return f"{direction_note} It is close to the Fed's target."


def pmi_signal(current: float, prior: float, sector: str) -> str:
    if current >= 50:
        base = f"{sector} activity is still expanding."
    else:
        base = f"{sector} activity is contracting."
    if current > prior:
        return f"{base} The pace improved versus the prior month."
    if current < prior:
        return f"{base} The pace slowed versus the prior month."
    return f"{base} The pace was unchanged versus the prior month."


def gdp_signal(current: float) -> str:
    if current < 1.0:
        return "Growth is weak on a quarterly annualized basis."
    if current < 2.0:
        return "Growth is positive but modest."
    return "Growth is running at a healthier pace."


def infer_target_range(effective_rate: float) -> tuple[float, float]:
    lower = math.floor(effective_rate * 4.0) / 4.0
    upper = lower + 0.25
    return lower, upper


def series_by_date(series: list[dict[str, Any]]) -> dict[date, float]:
    return {parse_iso_date(item["date"]): float(item["value"]) for item in series}


def pick_week_prior(series: list[dict[str, Any]]) -> dict[str, Any]:
    latest_date = parse_iso_date(series[0]["date"])
    target_date = latest_date - timedelta(days=7)
    for item in series[1:]:
        if parse_iso_date(item["date"]) <= target_date:
            return item
    return series[min(len(series) - 1, 5)]


@dataclass
class ScanRow:
    data_point: str
    current_value: str | None
    prior_reading: str | None
    direction: str | None
    signal_implication: str
    status: str
    source: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "data_point": self.data_point,
            "current_value": self.current_value,
            "prior_reading": self.prior_reading,
            "direction": self.direction,
            "signal_implication": self.signal_implication,
            "status": self.status,
            "source": self.source,
        }


class FmpClient:
    def __init__(
        self,
        api_key: str,
        daily_limit: int = DEFAULT_DAILY_LIMIT,
        state_path: Path = STATE_PATH,
    ) -> None:
        self.api_key = api_key
        self.daily_limit = daily_limit
        self.state_path = state_path
        self.state = self._load_state()
        self.calls_this_run = 0
        self.cache_hits_this_run = 0

    def _load_state(self) -> dict[str, Any]:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {
            "usage_date": utc_now().date().isoformat(),
            "daily_call_count": 0,
            "responses": {},
        }

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self.state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _reset_daily_usage_if_needed(self) -> None:
        today = utc_now().date().isoformat()
        if self.state.get("usage_date") != today:
            self.state["usage_date"] = today
            self.state["daily_call_count"] = 0

    def _cache_key(self, path: str, params: dict[str, Any]) -> str:
        return f"{path}?{urlencode(sorted(params.items()))}"

    def _touch_call(self) -> None:
        self._reset_daily_usage_if_needed()
        used = int(self.state.get("daily_call_count", 0))
        if used >= self.daily_limit:
            raise RuntimeError(
                f"Daily FMP call budget reached: {used}/{self.daily_limit}."
            )
        self.state["daily_call_count"] = used + 1
        self.calls_this_run += 1
        self._save_state()

    def _cache_entry_valid(self, entry: dict[str, Any], ttl_minutes: int) -> bool:
        fetched_at = entry.get("fetched_at")
        if not fetched_at:
            return False
        fetched = datetime.fromisoformat(fetched_at)
        return utc_now() - fetched <= timedelta(minutes=ttl_minutes)

    def _parse_payload(self, raw: str) -> Any:
        text = raw.strip()
        if text == "Invalid name":
            raise FmpInvalidNameError(text)
        if "Restricted Endpoint" in text or "Premium Query Parameter" in text:
            raise FmpRestrictedError(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise FmpApiError(f"Unexpected response payload: {text[:200]}") from exc

    def get_json(
        self,
        path: str,
        params: dict[str, Any],
        ttl_minutes: int,
        force_refresh: bool = False,
    ) -> Any:
        request_params = dict(params)
        request_params["apikey"] = self.api_key
        cache_key = self._cache_key(path, request_params)
        responses = self.state.setdefault("responses", {})
        entry = responses.get(cache_key)
        if entry and not force_refresh and self._cache_entry_valid(entry, ttl_minutes):
            self.cache_hits_this_run += 1
            return entry["data"]

        self._touch_call()
        url = f"{FMP_BASE_URL}{path}?{urlencode(request_params)}"
        request = Request(url, headers={"User-Agent": "research-macro-scan/1.0"})
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace").strip()
            if exc.code == 402 or "Restricted Endpoint" in payload or "Premium Query Parameter" in payload:
                raise FmpRestrictedError(payload) from exc
            raise FmpApiError(f"HTTP {exc.code}: {payload[:200]}") from exc
        except URLError as exc:
            raise FmpApiError(f"Network error: {exc}") from exc

        data = self._parse_payload(raw)
        responses[cache_key] = {
            "fetched_at": utc_now().isoformat(),
            "data": data,
        }
        self._save_state()
        return data

    @property
    def calls_used_today(self) -> int:
        self._reset_daily_usage_if_needed()
        return int(self.state.get("daily_call_count", 0))


class YahooFinanceClient:
    def __init__(self, state_path: Path = SECONDARY_STATE_PATH) -> None:
        self.state_path = state_path
        self.state = self._load_state()
        self.calls_this_run = 0
        self.cache_hits_this_run = 0

    def _load_state(self) -> dict[str, Any]:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {"responses": {}}

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self.state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _cache_entry_valid(self, entry: dict[str, Any], ttl_minutes: int) -> bool:
        fetched_at = entry.get("fetched_at")
        if not fetched_at:
            return False
        fetched = datetime.fromisoformat(fetched_at)
        return utc_now() - fetched <= timedelta(minutes=ttl_minutes)

    def get_chart(
        self,
        symbol: str,
        *,
        range_name: str = "5d",
        interval: str = "1d",
        ttl_minutes: int = 15,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        encoded_symbol = urlquote(symbol, safe="")
        url = (
            f"{YAHOO_CHART_BASE_URL}/{encoded_symbol}"
            f"?interval={interval}&range={range_name}"
        )
        responses = self.state.setdefault("responses", {})
        entry = responses.get(url)
        if entry and not force_refresh and self._cache_entry_valid(entry, ttl_minutes):
            self.cache_hits_this_run += 1
            return entry["data"]

        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace").strip()
            raise YahooFinanceError(f"HTTP {exc.code}: {body[:200]}") from exc
        except URLError as exc:
            raise YahooFinanceError(f"Network error: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise YahooFinanceError("Yahoo returned a non-JSON response.") from exc

        chart = payload.get("chart", {})
        error = chart.get("error")
        if error:
            description = error.get("description") or error.get("code") or str(error)
            raise YahooFinanceError(description)
        result = chart.get("result")
        if not result:
            raise YahooFinanceError(f"No chart result returned for {symbol}.")

        self.calls_this_run += 1
        data = result[0]
        responses[url] = {
            "fetched_at": utc_now().isoformat(),
            "data": data,
        }
        self._save_state()
        return data


class TradingEconomicsClient:
    def __init__(self, state_path: Path = TRADING_ECONOMICS_STATE_PATH) -> None:
        self.state_path = state_path
        self.state = self._load_state()
        self.calls_this_run = 0
        self.cache_hits_this_run = 0

    def _load_state(self) -> dict[str, Any]:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {"responses": {}}

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self.state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _cache_entry_valid(self, entry: dict[str, Any], ttl_minutes: int) -> bool:
        fetched_at = entry.get("fetched_at")
        if not fetched_at:
            return False
        fetched = datetime.fromisoformat(fetched_at)
        return utc_now() - fetched <= timedelta(minutes=ttl_minutes)

    def get_page(
        self,
        path: str,
        *,
        ttl_minutes: int = 360,
        force_refresh: bool = False,
    ) -> str:
        url = f"{TRADING_ECONOMICS_BASE_URL}{path}"
        responses = self.state.setdefault("responses", {})
        entry = responses.get(url)
        if entry and not force_refresh and self._cache_entry_valid(entry, ttl_minutes):
            self.cache_hits_this_run += 1
            return entry["data"]

        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(request, timeout=30) as response:
                html = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace").strip()
            raise TradingEconomicsError(f"HTTP {exc.code}: {body[:200]}") from exc
        except URLError as exc:
            raise TradingEconomicsError(f"Network error: {exc}") from exc

        self.calls_this_run += 1
        responses[url] = {
            "fetched_at": utc_now().isoformat(),
            "data": html,
        }
        self._save_state()
        return html


def unavailable_row(
    data_point: str,
    reason: str,
    source: dict[str, Any],
    proxy_note: str | None = None,
) -> ScanRow:
    implication = reason
    if proxy_note:
        implication = f"{reason} {proxy_note}"
    return ScanRow(
        data_point=data_point,
        current_value=None,
        prior_reading=None,
        direction=None,
        signal_implication=implication,
        status="unavailable",
        source=source,
    )


def fetch_single_quote(
    client: FmpClient,
    symbol: str,
    force_refresh: bool = False,
) -> dict[str, Any]:
    data = client.get_json(
        path="/quote",
        params={"symbol": symbol},
        ttl_minutes=15,
        force_refresh=force_refresh,
    )
    if not isinstance(data, list) or not data:
        raise FmpApiError(f"No quote data returned for {symbol}.")
    return data[0]


def fetch_indicator_series(
    client: FmpClient,
    name: str,
    limit: int | None = None,
    extra_params: dict[str, Any] | None = None,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"name": name}
    if limit is not None:
        params["limit"] = limit
    if extra_params:
        params.update(extra_params)
    data = client.get_json(
        path="/economic-indicators",
        params=params,
        ttl_minutes=1440,
        force_refresh=force_refresh,
    )
    if not isinstance(data, list) or len(data) < 2:
        raise FmpApiError(f"Indicator series {name} did not return enough rows.")
    return data


def fetch_treasury_rates(
    client: FmpClient,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    data = client.get_json(
        path="/treasury-rates",
        params={},
        ttl_minutes=720,
        force_refresh=force_refresh,
    )
    if not isinstance(data, list) or len(data) < 2:
        raise FmpApiError("Treasury rate series did not return enough rows.")
    return data


def fetch_light_history(
    client: FmpClient,
    symbol: str,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    data = client.get_json(
        path="/historical-price-eod/light",
        params={"symbol": symbol},
        ttl_minutes=60,
        force_refresh=force_refresh,
    )
    if not isinstance(data, list) or len(data) < 2:
        raise FmpApiError(f"Light history did not return enough rows for {symbol}.")
    return data


def last_non_null(values: list[Any]) -> float | None:
    for value in reversed(values):
        if value is not None:
            return float(value)
    return None


def previous_non_null(values: list[Any]) -> float | None:
    found_latest = False
    for value in reversed(values):
        if value is None:
            continue
        if not found_latest:
            found_latest = True
            continue
        return float(value)
    return None


def extract_meta_description(html: str) -> str:
    match = re.search(
        r'<meta id="metaDesc" name="description" content="([^"]+)"',
        html,
        flags=re.IGNORECASE,
    )
    if not match:
        raise TradingEconomicsError("Could not find page meta description.")
    return html_lib.unescape(match.group(1)).strip()


def extract_tradingeconomics_last_update(html: str) -> str | None:
    match = re.search(r"TELastUpdate\s*=\s*'(\d{14})'", html)
    if not match:
        return None
    raw = match.group(1)
    return datetime.strptime(raw, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat()


def infer_current_year(current_month: str, prior_month: str, prior_year: int) -> int:
    current_number = MONTH_NUMBERS[current_month]
    prior_number = MONTH_NUMBERS[prior_month]
    if current_number > prior_number:
        return prior_year
    if current_number < prior_number:
        return prior_year + 1
    return prior_year


def short_month_year(month_name: str, year: int) -> str:
    month_number = MONTH_NUMBERS[month_name]
    return date(year, month_number, 1).strftime("%b %Y")


def parse_tradingeconomics_release(
    description: str,
    unit_label: str,
) -> dict[str, Any]:
    patterns = [
        rf"in the United States (?:increased|decreased) to ([0-9.]+) {unit_label} in ([A-Za-z]+) from ([0-9.]+) {unit_label} in ([A-Za-z]+) of (\d{{4}})",
        rf"in the United States was unchanged at ([0-9.]+) {unit_label} in ([A-Za-z]+) from ([0-9.]+) {unit_label} in ([A-Za-z]+) of (\d{{4}})",
    ]
    for pattern in patterns:
        match = re.search(pattern, description, flags=re.IGNORECASE)
        if match:
            current_value = float(match.group(1))
            current_month = match.group(2)
            prior_value = float(match.group(3))
            prior_month = match.group(4)
            prior_year = int(match.group(5))
            current_year = infer_current_year(current_month, prior_month, prior_year)
            return {
                "current_value": current_value,
                "current_label": short_month_year(current_month, current_year),
                "prior_value": prior_value,
                "prior_label": short_month_year(prior_month, prior_year),
            }
    raise TradingEconomicsError(f"Could not parse release description: {description}")


def yahoo_snapshot(chart: dict[str, Any]) -> tuple[float, float, str]:
    meta = chart.get("meta", {})
    quote = (chart.get("indicators", {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    current = meta.get("regularMarketPrice")
    prior = meta.get("chartPreviousClose")
    if current is None:
        current = last_non_null(closes)
    if prior is None:
        prior = previous_non_null(closes)
    if current is None or prior is None:
        raise YahooFinanceError("Yahoo chart payload did not include current and prior prices.")
    market_time = meta.get("regularMarketTime")
    if market_time is None:
        timestamps = chart.get("timestamp") or []
        if not timestamps:
            raise YahooFinanceError("Yahoo chart payload did not include timestamps.")
        market_time = int(timestamps[-1])
    as_of = datetime.fromtimestamp(int(market_time), tz=timezone.utc).isoformat()
    return float(current), float(prior), as_of


def yahoo_wti_row(
    yahoo_client: YahooFinanceClient,
    force_refresh: bool = False,
) -> ScanRow:
    chart = yahoo_client.get_chart("CL=F", force_refresh=force_refresh)
    current, prior, as_of = yahoo_snapshot(chart)
    return ScanRow(
        data_point="WTI Crude Oil",
        current_value=format_currency(current, digits=2, suffix="/bbl"),
        prior_reading=f"{format_currency(prior, digits=2, suffix='/bbl')} (previous close)",
        direction=numeric_direction(current, prior, tolerance=0.05),
        signal_implication=oil_signal(current, prior),
        status="ok",
        source={
            "provider": "Yahoo Finance",
            "path": "/v8/finance/chart/CL=F",
            "url": f"{YAHOO_CHART_BASE_URL}/{urlquote('CL=F', safe='')}?interval=1d&range=5d",
            "as_of": as_of,
        },
    )


def yahoo_dxy_row(
    yahoo_client: YahooFinanceClient,
    force_refresh: bool = False,
) -> ScanRow:
    chart = yahoo_client.get_chart("DX-Y.NYB", force_refresh=force_refresh)
    current, prior, as_of = yahoo_snapshot(chart)
    return ScanRow(
        data_point="DXY Dollar Index",
        current_value=format_number(current, digits=3),
        prior_reading=f"{format_number(prior, digits=3)} (previous close)",
        direction=numeric_direction(current, prior, tolerance=0.005),
        signal_implication=dollar_signal(current, prior),
        status="ok",
        source={
            "provider": "Yahoo Finance",
            "path": "/v8/finance/chart/DX-Y.NYB",
            "url": f"{YAHOO_CHART_BASE_URL}/{urlquote('DX-Y.NYB', safe='')}?interval=1d&range=5d",
            "as_of": as_of,
        },
    )


def tradingeconomics_core_pce_row(
    te_client: TradingEconomicsClient,
    force_refresh: bool = False,
) -> ScanRow:
    path = "/united-states/core-pce-price-index-annual-change"
    html = te_client.get_page(path, force_refresh=force_refresh)
    description = extract_meta_description(html)
    parsed = parse_tradingeconomics_release(description, "percent")
    return ScanRow(
        data_point=f"Core PCE YoY ({parsed['current_label']})",
        current_value=format_percent(parsed["current_value"]),
        prior_reading=f"{format_percent(parsed['prior_value'])} ({parsed['prior_label']})",
        direction=numeric_direction(parsed["current_value"], parsed["prior_value"], tolerance=0.05),
        signal_implication=core_pce_signal(parsed["current_value"], parsed["prior_value"]),
        status="ok",
        source={
            "provider": "Trading Economics",
            "path": path,
            "url": f"{TRADING_ECONOMICS_BASE_URL}{path}",
            "as_of": extract_tradingeconomics_last_update(html),
            "note": "Parsed from the page meta description.",
        },
    )


def tradingeconomics_manufacturing_pmi_row(
    te_client: TradingEconomicsClient,
    force_refresh: bool = False,
) -> ScanRow:
    path = "/united-states/manufacturing-pmi"
    html = te_client.get_page(path, force_refresh=force_refresh)
    description = extract_meta_description(html)
    parsed = parse_tradingeconomics_release(description, "points")
    return ScanRow(
        data_point=f"ISM Manufacturing PMI ({parsed['current_label']})",
        current_value=format_number(parsed["current_value"], digits=2),
        prior_reading=f"{format_number(parsed['prior_value'], digits=2)} ({parsed['prior_label']})",
        direction=numeric_direction(parsed["current_value"], parsed["prior_value"], tolerance=0.05),
        signal_implication=pmi_signal(parsed["current_value"], parsed["prior_value"], "Manufacturing"),
        status="ok",
        source={
            "provider": "Trading Economics",
            "path": path,
            "url": f"{TRADING_ECONOMICS_BASE_URL}{path}",
            "as_of": extract_tradingeconomics_last_update(html),
            "note": "Parsed from the page meta description.",
        },
    )


def tradingeconomics_services_pmi_row(
    te_client: TradingEconomicsClient,
    force_refresh: bool = False,
) -> ScanRow:
    path = "/united-states/non-manufacturing-pmi"
    html = te_client.get_page(path, force_refresh=force_refresh)
    description = extract_meta_description(html)
    parsed = parse_tradingeconomics_release(description, "points")
    return ScanRow(
        data_point=f"ISM Services PMI ({parsed['current_label']})",
        current_value=format_number(parsed["current_value"], digits=2),
        prior_reading=f"{format_number(parsed['prior_value'], digits=2)} ({parsed['prior_label']})",
        direction=numeric_direction(parsed["current_value"], parsed["prior_value"], tolerance=0.05),
        signal_implication=pmi_signal(parsed["current_value"], parsed["prior_value"], "Services"),
        status="ok",
        source={
            "provider": "Trading Economics",
            "path": path,
            "url": f"{TRADING_ECONOMICS_BASE_URL}{path}",
            "as_of": extract_tradingeconomics_last_update(html),
            "note": "Parsed from the page meta description.",
        },
    )


def quote_row(
    data_point: str,
    symbol: str,
    digits: int,
    client: FmpClient,
    force_refresh: bool = False,
) -> ScanRow:
    quote = fetch_single_quote(client, symbol, force_refresh=force_refresh)
    current = float(quote["price"])
    prior = float(quote["previousClose"])
    as_of = datetime.fromtimestamp(int(quote["timestamp"]), tz=timezone.utc).isoformat()
    signal = vix_signal(current, prior) if data_point == "VIX" else price_signal(data_point, current, prior)
    return ScanRow(
        data_point=data_point,
        current_value=format_number(current, digits=digits),
        prior_reading=f"{format_number(prior, digits=digits)} (previous close)",
        direction=numeric_direction(current, prior, tolerance=0.005),
        signal_implication=signal,
        status="ok",
        source={
            **build_source("/quote", {"symbol": symbol}),
            "as_of": as_of,
        },
    )


def build_fmp_rows(
    client: FmpClient,
    force_refresh: bool = False,
    use_brent_proxy: bool = False,
) -> list[ScanRow]:
    rows: list[ScanRow] = []

    rows.append(quote_row("S&P 500", "^GSPC", digits=2, client=client, force_refresh=force_refresh))
    rows.append(quote_row("Nasdaq", "^IXIC", digits=2, client=client, force_refresh=force_refresh))
    rows.append(quote_row("Russell 2000", "^RUT", digits=2, client=client, force_refresh=force_refresh))
    rows.append(quote_row("VIX", "^VIX", digits=2, client=client, force_refresh=force_refresh))

    fed_series = fetch_indicator_series(client, "federalFunds", limit=12, force_refresh=force_refresh)
    current_effective = float(fed_series[0]["value"])
    prior_effective = float(fed_series[1]["value"])
    current_lower, current_upper = infer_target_range(current_effective)
    prior_lower, prior_upper = infer_target_range(prior_effective)
    rows.append(
        ScanRow(
            data_point="Fed Funds Rate",
            current_value=format_rate_range(current_lower, current_upper),
            prior_reading=format_rate_range(prior_lower, prior_upper),
            direction=range_direction(current_lower, current_upper, prior_lower, prior_upper),
            signal_implication=fed_signal(current_lower, current_upper, prior_lower, prior_upper),
            status="derived",
            source={
                **build_source("/economic-indicators", {"name": "federalFunds", "limit": 12}),
                "latest_effective_rate": format_percent(current_effective),
                "note": "Target band inferred from the effective federal funds rate because FMP free tier exposes the effective series, not the target range.",
            },
        )
    )

    treasury = fetch_treasury_rates(client, force_refresh=force_refresh)
    latest_treasury = treasury[0]
    prior_week_treasury = pick_week_prior(treasury)
    current_10y = float(latest_treasury["year10"])
    prior_10y = float(prior_week_treasury["year10"])
    current_2y = float(latest_treasury["year2"])
    prior_2y = float(prior_week_treasury["year2"])
    current_spread = current_10y - current_2y
    prior_spread = prior_10y - prior_2y

    rows.append(
        ScanRow(
            data_point="10Y Treasury Yield",
            current_value=format_percent(current_10y),
            prior_reading=f"{format_percent(prior_10y)} (one week earlier)",
            direction=numeric_direction(current_10y, prior_10y, tolerance=0.005),
            signal_implication=treasury_signal(current_10y, prior_10y, "10Y"),
            status="ok",
            source={
                **build_source("/treasury-rates", {}),
                "as_of": latest_treasury["date"],
            },
        )
    )
    rows.append(
        ScanRow(
            data_point="2Y Treasury Yield",
            current_value=format_percent(current_2y),
            prior_reading=f"{format_percent(prior_2y)} (one week earlier)",
            direction=numeric_direction(current_2y, prior_2y, tolerance=0.005),
            signal_implication=treasury_signal(current_2y, prior_2y, "2Y"),
            status="ok",
            source={
                **build_source("/treasury-rates", {}),
                "as_of": latest_treasury["date"],
            },
        )
    )
    rows.append(
        ScanRow(
            data_point="10Y-2Y Spread",
            current_value=format_signed_percent(current_spread),
            prior_reading=f"{format_signed_percent(prior_spread)} (one week earlier)",
            direction=numeric_direction(current_spread, prior_spread, tolerance=0.005),
            signal_implication=spread_signal(current_spread),
            status="derived",
            source={
                **build_source("/treasury-rates", {}),
                "as_of": latest_treasury["date"],
            },
        )
    )

    cpi_params = {
        "from": date(utc_now().year - 2, 1, 1).isoformat(),
        "to": utc_now().date().isoformat(),
    }
    cpi_series = fetch_indicator_series(
        client,
        "CPI",
        extra_params=cpi_params,
        force_refresh=force_refresh,
    )
    cpi_lookup = series_by_date(cpi_series)
    current_cpi_date = parse_iso_date(cpi_series[0]["date"])
    prior_cpi_date = parse_iso_date(cpi_series[1]["date"])
    current_cpi = float(cpi_series[0]["value"])
    prior_cpi = float(cpi_series[1]["value"])
    current_cpi_yoy = ((current_cpi / cpi_lookup[start_of_same_month_last_year(current_cpi_date)]) - 1.0) * 100.0
    prior_cpi_yoy = ((prior_cpi / cpi_lookup[start_of_same_month_last_year(prior_cpi_date)]) - 1.0) * 100.0
    rows.append(
        ScanRow(
            data_point=f"CPI YoY ({current_cpi_date.strftime('%b %Y')})",
            current_value=format_percent(current_cpi_yoy),
            prior_reading=f"{format_percent(prior_cpi_yoy)} ({prior_cpi_date.strftime('%b %Y')})",
            direction=numeric_direction(current_cpi_yoy, prior_cpi_yoy, tolerance=0.05),
            signal_implication=inflation_signal(current_cpi_yoy),
            status="derived",
            source={
                **build_source("/economic-indicators", {"name": "CPI", **cpi_params}),
                "note": "YoY CPI is derived from the monthly CPI index because FMP free tier returns the index level rather than the precomputed YoY rate.",
            },
        )
    )

    rows.append(
        unavailable_row(
            data_point="Core PCE YoY",
            reason="Unavailable on the tested FMP free-tier endpoints.",
            source=build_source("/economic-indicators", {"name": "corePCE"}),
        )
    )

    rows.append(
        unavailable_row(
            data_point="ISM Manufacturing PMI",
            reason="Unavailable on the tested FMP free-tier endpoints.",
            source=build_source("/economic-indicators", {"name": "manufacturingPMI"}),
        )
    )

    rows.append(
        unavailable_row(
            data_point="ISM Services PMI",
            reason="Unavailable on the tested FMP free-tier endpoints.",
            source=build_source("/economic-indicators", {"name": "servicesPMI"}),
        )
    )

    unemployment_series = fetch_indicator_series(client, "unemploymentRate", limit=12, force_refresh=force_refresh)
    current_unemployment = float(unemployment_series[0]["value"])
    prior_unemployment = float(unemployment_series[1]["value"])
    current_unemployment_date = parse_iso_date(unemployment_series[0]["date"])
    prior_unemployment_date = parse_iso_date(unemployment_series[1]["date"])
    rows.append(
        ScanRow(
            data_point=f"Unemployment Rate ({current_unemployment_date.strftime('%b %Y')})",
            current_value=format_percent(current_unemployment),
            prior_reading=f"{format_percent(prior_unemployment)} ({prior_unemployment_date.strftime('%b %Y')})",
            direction=numeric_direction(current_unemployment, prior_unemployment, tolerance=0.05),
            signal_implication=unemployment_signal(current_unemployment),
            status="ok",
            source=build_source("/economic-indicators", {"name": "unemploymentRate", "limit": 12}),
        )
    )

    claims_series = fetch_indicator_series(client, "initialClaims", limit=8, force_refresh=force_refresh)
    current_claims = float(claims_series[0]["value"])
    prior_claims = float(claims_series[1]["value"])
    current_claims_date = parse_iso_date(claims_series[0]["date"])
    rows.append(
        ScanRow(
            data_point=f"Initial Jobless Claims ({current_claims_date.isoformat()})",
            current_value=format_thousands(current_claims),
            prior_reading=f"{format_thousands(prior_claims)} (prior week)",
            direction=numeric_direction(current_claims, prior_claims, tolerance=500),
            signal_implication=claims_signal(current_claims),
            status="ok",
            source=build_source("/economic-indicators", {"name": "initialClaims", "limit": 8}),
        )
    )

    if use_brent_proxy:
        brent_history = fetch_light_history(client, "BZUSD", force_refresh=force_refresh)
        current_brent = float(brent_history[0]["price"])
        prior_brent = float(brent_history[1]["price"])
        rows.append(
            ScanRow(
                data_point="WTI Crude Oil",
                current_value=format_currency(current_brent, digits=2, suffix="/bbl"),
                prior_reading=f"{format_currency(prior_brent, digits=2, suffix='/bbl')} (Brent proxy prior close)",
                direction=numeric_direction(current_brent, prior_brent, tolerance=0.05),
                signal_implication="Using Brent crude as a proxy because the FMP CLUSD route is unavailable on the free tier.",
                status="proxy",
                source={
                    **build_source("/historical-price-eod/light", {"symbol": "BZUSD"}),
                    "note": "Brent proxy substituted for blocked WTI symbol CLUSD.",
                },
            )
        )
    else:
        rows.append(
            unavailable_row(
                data_point="WTI Crude Oil",
                reason="CLUSD is paywalled on the tested FMP free-tier endpoints.",
                proxy_note="Yahoo or another provider can replace this row during merge.",
                source=build_source("/quote", {"symbol": "CLUSD"}),
            )
        )

    gold_quote = fetch_single_quote(client, "GCUSD", force_refresh=force_refresh)
    current_gold = float(gold_quote["price"])
    prior_gold = float(gold_quote["previousClose"])
    rows.append(
        ScanRow(
            data_point="Gold Price",
            current_value=format_currency(current_gold, digits=2, suffix="/oz"),
            prior_reading=f"{format_currency(prior_gold, digits=2, suffix='/oz')} (previous close)",
            direction=numeric_direction(current_gold, prior_gold, tolerance=0.05),
            signal_implication=gold_signal(current_gold, prior_gold),
            status="ok",
            source={
                **build_source("/quote", {"symbol": "GCUSD"}),
                "as_of": datetime.fromtimestamp(int(gold_quote["timestamp"]), tz=timezone.utc).isoformat(),
            },
        )
    )

    rows.append(
        unavailable_row(
            data_point="DXY Dollar Index",
            reason="DX-Y.NYB is paywalled on the tested FMP free-tier endpoints.",
            proxy_note="Yahoo or another provider can replace this row during merge.",
            source=build_source("/quote", {"symbol": "DX-Y.NYB"}),
        )
    )

    real_gdp_series = fetch_indicator_series(client, "realGDP", limit=4, force_refresh=force_refresh)
    current_real_gdp = float(real_gdp_series[0]["value"])
    prior_real_gdp = float(real_gdp_series[1]["value"])
    earlier_real_gdp = float(real_gdp_series[2]["value"])
    gdp_growth = annualized_quarterly_growth(current_real_gdp, prior_real_gdp)
    prior_gdp_growth = annualized_quarterly_growth(prior_real_gdp, earlier_real_gdp)
    current_gdp_date = parse_iso_date(real_gdp_series[0]["date"])
    prior_gdp_date = parse_iso_date(real_gdp_series[1]["date"])
    rows.append(
        ScanRow(
            data_point=f"US GDP {quarter_label(current_gdp_date)} (annualized, derived)",
            current_value=format_percent(gdp_growth),
            prior_reading=f"{format_percent(prior_gdp_growth)} ({quarter_label(prior_gdp_date)})",
            direction=numeric_direction(gdp_growth, prior_gdp_growth, tolerance=0.05),
            signal_implication=(
                gdp_signal(gdp_growth)
                + " Derived from the quarterly real GDP series; estimate revision history is not exposed on FMP free tier."
            ),
            status="derived",
            source={
                **build_source("/economic-indicators", {"name": "realGDP", "limit": 4}),
                "note": "Quarterly annualized growth derived from the latest two real GDP observations.",
            },
        )
    )

    return rows


def build_yahoo_rows(
    yahoo_client: YahooFinanceClient,
    force_refresh: bool = False,
) -> list[ScanRow]:
    rows: list[ScanRow] = []
    try:
        rows.append(yahoo_wti_row(yahoo_client, force_refresh=force_refresh))
    except YahooFinanceError as exc:
        rows.append(
            unavailable_row(
                data_point="WTI Crude Oil",
                reason="Yahoo CL=F fallback was unavailable.",
                proxy_note=str(exc),
                source={
                    "provider": "Yahoo Finance",
                    "path": "/v8/finance/chart/CL=F",
                    "url": f"{YAHOO_CHART_BASE_URL}/{urlquote('CL=F', safe='')}?interval=1d&range=5d",
                },
            )
        )
    try:
        rows.append(yahoo_dxy_row(yahoo_client, force_refresh=force_refresh))
    except YahooFinanceError as exc:
        rows.append(
            unavailable_row(
                data_point="DXY Dollar Index",
                reason="Yahoo DX-Y.NYB fallback was unavailable.",
                proxy_note=str(exc),
                source={
                    "provider": "Yahoo Finance",
                    "path": "/v8/finance/chart/DX-Y.NYB",
                    "url": f"{YAHOO_CHART_BASE_URL}/{urlquote('DX-Y.NYB', safe='')}?interval=1d&range=5d",
                },
            )
        )
    return rows


def build_tradingeconomics_rows(
    te_client: TradingEconomicsClient,
    force_refresh: bool = False,
) -> list[ScanRow]:
    rows: list[ScanRow] = []
    builders = [
        ("Core PCE YoY", tradingeconomics_core_pce_row, "/united-states/core-pce-price-index-annual-change"),
        ("ISM Manufacturing PMI", tradingeconomics_manufacturing_pmi_row, "/united-states/manufacturing-pmi"),
        ("ISM Services PMI", tradingeconomics_services_pmi_row, "/united-states/non-manufacturing-pmi"),
    ]
    for data_point, builder, path in builders:
        try:
            rows.append(builder(te_client, force_refresh=force_refresh))
        except TradingEconomicsError as exc:
            rows.append(
                unavailable_row(
                    data_point=data_point,
                    reason="Trading Economics fallback was unavailable.",
                    proxy_note=str(exc),
                    source={
                        "provider": "Trading Economics",
                        "path": path,
                        "url": f"{TRADING_ECONOMICS_BASE_URL}{path}",
                    },
                )
            )
    return rows


def build_provider_output(
    provider: str,
    rows: list[ScanRow],
    calls_made_this_run: int,
    cache_hits_this_run: int,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row_keys = [row_merge_key(row.data_point) for row in rows]
    payload = {
        "provider": provider,
        "calls_made_this_run": calls_made_this_run,
        "cache_hits_this_run": cache_hits_this_run,
        "row_keys": row_keys,
        "limitations": sorted(
            {
                row_merge_key(row.data_point)
                for row in rows
                if row.status == "unavailable"
            }
        ),
        "rows": [row.as_dict() for row in rows],
    }
    if extra:
        payload.update(extra)
    return payload


def row_merge_key(data_point: str) -> str:
    for prefix in ROW_ORDER:
        if data_point == prefix:
            return prefix
        if data_point.startswith(f"{prefix} ("):
            return prefix
        if prefix == "US GDP" and data_point.startswith("US GDP"):
            return prefix
    return data_point


def merge_provider_rows(provider_outputs: list[dict[str, Any]]) -> list[ScanRow]:
    merged: dict[str, ScanRow] = {}
    for provider_output in provider_outputs:
        for row_payload in provider_output["rows"]:
            row = ScanRow(
                data_point=row_payload["data_point"],
                current_value=row_payload["current_value"],
                prior_reading=row_payload["prior_reading"],
                direction=row_payload["direction"],
                signal_implication=row_payload["signal_implication"],
                status=row_payload["status"],
                source=row_payload["source"],
            )
            key = row_merge_key(row.data_point)
            existing = merged.get(key)
            if existing is None:
                merged[key] = row
                continue
            if existing.status == "unavailable" and row.status != "unavailable":
                merged[key] = row
                continue
            if existing.status == "proxy" and row.status == "ok":
                merged[key] = row
    ordered_rows: list[ScanRow] = []
    for key in ROW_ORDER:
        row = merged.get(key)
        if row is not None:
            ordered_rows.append(row)
    for key, row in merged.items():
        if key not in ROW_ORDER:
            ordered_rows.append(row)
    return ordered_rows


def build_macro_scan_payload(
    client: FmpClient,
    yahoo_client: YahooFinanceClient,
    te_client: TradingEconomicsClient,
    force_refresh: bool = False,
    use_brent_proxy: bool = False,
) -> dict[str, Any]:
    fmp_rows = build_fmp_rows(
        client,
        force_refresh=force_refresh,
        use_brent_proxy=use_brent_proxy,
    )
    yahoo_rows = build_yahoo_rows(
        yahoo_client,
        force_refresh=force_refresh,
    )
    te_rows = build_tradingeconomics_rows(
        te_client,
        force_refresh=force_refresh,
    )
    provider_outputs = [
        build_provider_output(
            "Financial Modeling Prep",
            fmp_rows,
            client.calls_this_run,
            client.cache_hits_this_run,
            extra={
                "daily_limit": client.daily_limit,
                "calls_used_today": client.calls_used_today,
            },
        ),
        build_provider_output(
            "Yahoo Finance",
            yahoo_rows,
            yahoo_client.calls_this_run,
            yahoo_client.cache_hits_this_run,
        ),
        build_provider_output(
            "Trading Economics",
            te_rows,
            te_client.calls_this_run,
            te_client.cache_hits_this_run,
        ),
    ]
    rows = merge_provider_rows(provider_outputs)
    unavailable = [row.data_point for row in rows if row.status == "unavailable"]
    proxies = [row.data_point for row in rows if row.status == "proxy"]
    derived = [row.data_point for row in rows if row.status == "derived"]
    return {
        "function": "research-macro-scan",
        "generated_at": utc_now().isoformat(),
        "providers": [output["provider"] for output in provider_outputs],
        "free_tier_daily_limit": client.daily_limit,
        "calls_made_this_run": client.calls_this_run,
        "cache_hits_this_run": client.cache_hits_this_run,
        "calls_used_today": client.calls_used_today,
        "secondary_calls_made_this_run": yahoo_client.calls_this_run,
        "secondary_cache_hits_this_run": yahoo_client.cache_hits_this_run,
        "tertiary_calls_made_this_run": te_client.calls_this_run,
        "tertiary_cache_hits_this_run": te_client.cache_hits_this_run,
        "provider_outputs": provider_outputs,
        "rows": [row.as_dict() for row in rows],
        "limitations": unavailable,
        "proxy_rows": proxies,
        "derived_rows": derived,
    }


def research_macro_scan(
    output_path: str | os.PathLike[str] = DEFAULT_OUTPUT_PATH,
    *,
    api_key: str | None = None,
    daily_limit: int = DEFAULT_DAILY_LIMIT,
    force_refresh: bool = False,
    use_brent_proxy: bool = False,
    strict: bool = False,
) -> dict[str, Any]:
    client = FmpClient(
        api_key=resolve_fmp_api_key(api_key),
        daily_limit=daily_limit,
    )
    yahoo_client = YahooFinanceClient()
    te_client = TradingEconomicsClient()
    payload = build_macro_scan_payload(
        client,
        yahoo_client,
        te_client,
        force_refresh=force_refresh,
        use_brent_proxy=use_brent_proxy,
    )
    if strict and payload["limitations"]:
        missing = ", ".join(payload["limitations"])
        raise RuntimeError(f"Strict mode failed; unavailable rows: {missing}")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


API_FUNCTIONS = {
    "research-macro-scan": research_macro_scan,
}


def invoke_api_function(name: str, **kwargs: Any) -> dict[str, Any]:
    try:
        handler = API_FUNCTIONS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown API function: {name}") from exc
    return handler(**kwargs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run research helper functions.")
    parser.add_argument(
        "function_name",
        nargs="?",
        default="research-macro-scan",
        choices=sorted(API_FUNCTIONS.keys()),
        help="Registered function to execute.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Where to write the JSON payload.",
    )
    parser.add_argument(
        "--daily-limit",
        type=int,
        default=DEFAULT_DAILY_LIMIT,
        help="Local guardrail for FMP calls per UTC day.",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Bypass the local response cache.",
    )
    parser.add_argument(
        "--use-brent-proxy",
        action="store_true",
        help="Use Brent crude as a proxy for blocked WTI pricing.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if any requested rows are unavailable on the free tier.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = invoke_api_function(
        args.function_name,
        output_path=args.output,
        daily_limit=args.daily_limit,
        force_refresh=args.force_refresh,
        use_brent_proxy=args.use_brent_proxy,
        strict=args.strict,
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
