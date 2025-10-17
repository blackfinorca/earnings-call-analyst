"""Generate a consolidated earnings JSON file for the frontend."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .cache import CACHE_DIR, load_cache, load_latest_enrichment
from .pipeline import augment_rows
from .utils import now_sgt

LOGGER = logging.getLogger("app.generate")
logging.basicConfig(level=logging.INFO)

OUTPUT_PATH = Path("src/data/earnings_data.json")


def latest_earnings_path() -> Path:
    files = sorted(CACHE_DIR.glob("yahoo_earnings_*.json"), reverse=True)
    if not files:
        raise FileNotFoundError("No earnings cache files found. Run `python -m app.refresh` first.")
    return files[0]


def build_payload() -> dict:
    earnings_path = latest_earnings_path()
    payload = load_cache(earnings_path)
    if payload is None:
        raise ValueError(f"Failed to load earnings cache: {earnings_path}")

    enrichment = load_latest_enrichment() or {}
    ticker_map = enrichment.get("tickers", {})
    augment_rows(payload.get("days", []), ticker_map)

    payload["generated_at"] = now_sgt().isoformat()
    payload["source"] = "Yahoo Finance"
    return payload


def write_payload(payload: dict, output: Path = OUTPUT_PATH) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
    LOGGER.info("Wrote %s", output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate consolidated earnings JSON")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Path to write JSON (default src/data/earnings_data.json)")
    args = parser.parse_args()

    payload = build_payload()
    write_payload(payload, args.output)


if __name__ == "__main__":  # pragma: no cover
    main()
