# Yahoo Earnings Calendar Service

A lightweight FastAPI service that scrapes the Yahoo Finance earnings calendar for the next seven days (configurable), caches the results on disk for 24 hours, and exposes them through a REST endpoint that is safe to consume from front-end applications.

## Features

- **Playwright-powered scraper** (Chromium) with rotating user agents, randomized delays, and retry/backoff logic.
- **Disk cache** (`./cache/…`) to avoid unnecessary scraping for 24 hours per date range.
- **FastAPI endpoint** (`GET /api/earnings`) with optional `start` and `days` query parameters.
- **APScheduler** refresh job every day at 06:00 Asia/Singapore that pre-warms the default (today → +7 days) cache.
- **Structured JSON response** with daily breakdown, row counts, and error reporting.

## Project layout

```
app/
  cache.py       # Cache helpers
  main.py        # FastAPI app, scheduler
  scraper.py     # Playwright Yahoo scraper
  utils.py       # Timezone & helper utilities
cache/           # Cache files created at runtime
requirements.txt
.env.example
tests/
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

Create an `.env` file if you need to override defaults:

```
PORT=3000
TZ=Asia/Singapore
```

## Running locally

Collect everything via CLI scripts and consume the generated JSON directly:

```bash
# 1. Refresh Yahoo earnings calendar (requires Playwright scrape)
python -m app.refresh

# 2. (Optional) Enrich tickers with current price/EPS/revenue via yfinance
python -m app.enrich --force

# 3. Compose the single JSON the frontend reads
python -m app.generate
```

The final consolidated file lives at `src/data/earnings_data.json`.

### Front-end usage

```js
import earnings from '../data/earnings_data.json';
```

The dashboard flattens the `days` array from this JSON and renders it—no API server required.

## Enrichment job

Generate per-ticker price and estimate data using yfinance:

```bash
python -m app.enrich
```

Optional flags:

- `--force` – ignore existing enrichment cache and rescrape.
- `--max-concurrency N` – adjust concurrency (default 3 for yfinance lookups).

Output is written to `./cache/yahoo_enriched_<YYYY-MM-DD>.json`.

## Testing

Run the lightweight test suite:

```bash
pytest
```

Tests cover cache freshness logic, the local number parser, and the supporting helpers.
