"""Helper utilities for composing normalized earnings payloads."""
from __future__ import annotations

from typing import Any, Dict

from .utils import parse_number


def augment_rows(days: list[dict[str, Any]], ticker_map: Dict[str, Any]) -> None:
    """Merge enrichment data into each row and normalize numeric fields."""
    for day in days:
        for row in day.get("rows", []):
            symbol = (row.get("symbol") or row.get("ticker") or "").strip().upper()
            info = ticker_map.get(symbol) if symbol else None
            if info:
                if info.get("price") is not None:
                    row["stockPrice"] = info["price"]
                if info.get("eps_estimate_curr_q") is not None:
                    row["epsEstimate"] = info["eps_estimate_curr_q"]
                if info.get("revenue_estimate_curr_q") is not None:
                    row["revenueEstimate"] = info["revenue_estimate_curr_q"]
            row.setdefault("epsEstimate", parse_number(row.get("eps_estimate")))
            row.setdefault("revenueEstimate", parse_number(row.get("revenue_estimate")))
            row.setdefault("stockPrice", parse_number(row.get("stock_price")))
