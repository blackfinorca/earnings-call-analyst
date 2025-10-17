# Yahoo Earnings Calendar Static Pipeline

Generate a static JSON feed of upcoming earnings using RapidAPI and yfinance, then serve it directly to the React dashboard—no backend server required.

## Features

- Fetch the Yahoo Finance earnings calendar via RapidAPI (`app.refresh`).
- Enrich each ticker with price/EPS/revenue using yfinance (`app.enrich`).
- Produce a single JSON file under `src/data/earnings_data_<date>.json` that the frontend imports directly.
- Keep historical payloads in `cache/` for reference or regeneration (`app.generate`).

## Project layout

```
app/
  cache.py         # Cache helpers
  enrich.py        # yfinance enrichment + JSON update
  pipeline.py      # Shared augmentation helpers
  refresh.py       # RapidAPI calendar fetcher
  utils.py         # Timezone & helper utilities
cache/             # Cached payloads (written by scripts)
requirements.txt
.env.example
src/data/          # Frontend JSON files
src/utils/dataClient.js  # Imports the active JSON
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Provide your RapidAPI credentials via environment or `.env`:

```
RAPIDAPI_KEY=f3ba37d23bmsh7f5f08200423752p124129jsn859ceeb7bbd1
```

## Workflow

1. **Fetch the calendar**
   ```bash
   python -m app.refresh --date 2025-10-17 --days 1
   ```
   This hits the RapidAPI endpoint, writes `src/data/earnings_data_2025-10-17.json`, updates `src/data/earnings_data.json`, and rewires `src/utils/dataClient.js` to import the dated file.

2. **(Optional) Enrich with yfinance**
   ```bash
   python -m app.enrich --force
   ```
   Adds price/EPS/revenue for every ticker and updates both the dated JSON and `earnings_data.json`.

3. **(Optional) Rebuild from cached files**
   ```bash
   python -m app.generate
   ```
   Useful if you have an older `cache/yahoo_earnings_*.json` snapshot and want to regenerate the frontend JSON.

The React app simply imports the generated JSON; start it with your usual Vite workflow:

```bash
npm install        # first time
npm start          # Vite dev server
```

## Tests

```bash
pytest
```

Covers cache freshness logic, number parsing, and helper utilities.
