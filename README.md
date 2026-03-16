# Investment Strategy Research

Research app workspace with a separated backend scan module, frontend prototype, and persisted data outputs.

## Phases

Phase deliverables can live in their own folders.

## Structure

```text
M1 macro scan/
  research-functions.py
  research-macro-scan.json
M2 Sector ranking/
  sector-ranking.py
backend/
  research_app/
    scans/
      macro_scan.py
data/
  state/
    fmp-state.json
    yahoo-state.json
    tradingeconomics-state.json
frontend/
  src/
    prototypes/
      investment-strategy-research.jsx
```

## Usage

Run the phase entrypoint from the repo root:

```bash
python3 "M1 macro scan/research-functions.py" research-macro-scan
```

The generated scan is written to `M1 macro scan/research-macro-scan.json`.

The next phase scaffold is available at `M2 Sector ranking/sector-ranking.py`.

## Configuration

Store secrets in `.env` at the project root. The macro scan expects:

```bash
FMP_API_KEY=your_key_here
```
