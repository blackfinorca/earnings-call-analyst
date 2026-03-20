# M3b Screening & Scoring

## Runtime Context

Input: `M3B Screening/universe-generation-api.json`
Output: `M3B Screening/stock-screener.txt`

Read `stocks` array only. Ignore `flagged_stocks` and
`fetch_failures`. Pull `rotation_score`, `cycle_phase`,
`favored_sectors`, and `avoid_sectors` from the input
and from `M3A Universe generation/universe-generation.json`.

Execute silently. No confirmations.

**CRITICAL OUTPUT RULE**: Do NOT write your reasoning,
working calculations, intermediate scoring steps, or
scratch work to the output. Keep all computation
internal. Output ONLY the final structured report
starting with PRE-OUTPUT CHECKS. The first line of
your response must be "PRE-OUTPUT CHECKS".

---

## Scoring Rules

### Lens 1 — Sector Rotation (0-3)

Match `sector` to M3a rank. Use M3a label if yfinance
sector conflicts (note "label corrected" in Notes).

| Score | Condition |
|---|---|
| 3 | Rank 1-2 sector AND rotation_score ≤ -1 |
| 2 | Rank 3-4 sector |
| 1 | Neutral sector |
| 0 | Avoided sector — stock cannot advance |

### Lens 2 — Macro Alignment (0-3)

Three active M2 themes. Score by how many the stock
benefits from.

| Theme | BENEFITS if | HURT if |
|---|---|---|
| Stagflation / pricing power | gross_margin > 40% AND revenue_growth > 0% | gross_margin < 20% AND revenue_growth ≤ 0% |
| Fed paralysis / high rates | debt_to_ebitda < 1.5 AND fcf_yield > 3% | debt_to_ebitda > 3.0 |
| Oil shock | Energy sector AND industry contains "Integrated" or "Refin" | Industrials, Transportation, or Chemicals |

| Score | Condition |
|---|---|
| 3 | Benefits from 2+ themes |
| 2 | Benefits from 1 theme |
| 1 | Neutral to all |
| 0 | Hurt by any theme |

### Lens 3 — Multi-Factor Score (0-10)

Rank all stocks against each other. Convert each to
percentile within the universe using:
`pct = (n - rank) / (n - 1) × 100`

| Factor | Field | Direction | Fallback |
|---|---|---|---|
| Value | `pe_forward` | Lower = better | Use pe_trailing; if both null → 25th pct, flag |
| Momentum | `momentum_score` (return_12m minus return_1m) | Higher = better | Calculate from components; if both null → 50th pct, flag |
| Quality | `roe / (1 + abs(debt_to_equity))` | Higher = better | If D/E negative or null: use `roe / (1 + debt_to_ebitda)`, note "D/E substituted"; if roe null → 25th pct, flag |

`Factor Score = avg(Value pct, Momentum pct, Quality pct) / 10`
Round to one decimal.

### Lens 4 — Quality Growth (0-6 → A/B/C/F)

Six binary checks. Pass = 1, Fail = 0.

| # | Field | Pass | Fallback |
|---|---|---|---|
| 1 | `roe` | > 15% | FAIL, flag |
| 2 | `gross_margin_pct` | > 40% (see adjusted thresholds) | FAIL, flag |
| 3 | `debt_to_equity` | < 1.0 | Use debt_to_ebitda < 2.0 |
| 4 | `free_cash_flow_ttm` | > 0 | FAIL, flag |
| 5 | `revenue_growth_yoy` | > 5% | FAIL, flag |
| 6 | `gross_margin_pct` > 40% AND `operating_margin_pct` > 15% | Both required | FAIL if either null |

Adjusted Check 2 thresholds:
- Food retail / Discount Stores: > 20%
- Energy Integrated: > 15%

Grades: 5-6 = A (pts 3), 3-4 = B (pts 2), 2 = C (pts 1),
0-1 = F (pts 0)

### Lens 5 — Diversification (tiebreaker only)

Run after scoring Lenses 1-4. Classify against top 10.

- DIVERSIFIER: sector OR industry_gics not in top 10
- CONCENTRATOR: both sector AND industry_gics overlap
  with 2+ top-10 stocks

Equal composite scores: DIVERSIFIER wins.

### Composite Formula
```
Total = (Rotation × 2) + (Macro × 2) +
        (Factor × 1) + (Quality Pts × 3)
```

Max = 31. Thresholds: 25+ = Exceptional, 20-24 = Strong,
15-19 = Conditional, below 15 = Eliminated.

---

## Reasoning Check

Run after composite ranking, before confirming any ADVANCE.
This is a gate, not commentary. Document every demotion.

**A — Individual Stock Tests**

| Test | Flag if | Action |
|---|---|---|
| A1: Momentum vs cycle | return_3m_pct < -5% in Late Cycle / Stagflation | Demote to WATCHLIST unless rsi_14d < 35 |
| A2: Leverage vs rates | debt_to_ebitda > 4.0 AND rotation_score ≤ -1 | Demote to WATCHLIST, flag for Phase 4 |
| A3: Payout sustainability | payout_ratio > 100% AND (FCF / (div_yield × mktcap)) < 0.7 | Demote to WATCHLIST |
| A4: Valuation vs cycle | pe_forward > 30 AND cycle = Late Cycle | Require Rotation = 3 AND Macro = 3 to stay ADVANCE; else demote |

**B — Portfolio-Level Tests**

| Test | Check | Flag |
|---|---|---|
| B1: Sub-industry concentration | Count stocks sharing same industry_gics in advance list | If 3+ share same industry_gics: CONCENTRATED IN SUB-INDUSTRY — note for Phase 4 |
| B2: Oil reversal risk | Highest debt_to_ebitda among advancing Energy stocks | Flag as: "OIL REVERSAL RISK — first Energy exit if WTI < $75" |
| B3: Portfolio beta | Avg beta of all advancing stocks | If avg beta > 0.7: flag highest-beta stock for position size reduction in Phase 5 |

**C — Macro Reconciliation**

| Rule | Check | Action |
|---|---|---|
| C1: Rotation alignment | % of advancing stocks in Healthcare, Utilities, or Staples | If < 50% and rotation_score ≤ -1: flag PORTFOLIO MISALIGNED |
| C2: Energy tactical cap | Count advancing Energy stocks | If > 3: demote lowest-scoring Energy stock to WATCHLIST — M2 labels Energy tactical, not core |
| C3: Missing favored sector | Check if Utilities represented in advance list | If zero Utilities: promote highest-scoring Utility from WATCHLIST, displace lowest ADVANCE stock |

---

## Pre-Output Checks

Run before writing any section. Report results under
PRE-OUTPUT CHECKS at the top of the file.

1. **Lens 5 list:** Classify every stock DIVERSIFIER /
   CONCENTRATOR before the scoring table.
2. **Sector cap:** Max 4 per sector in ADVANCE. State
   initial and final distribution. List demotions.
3. **Consistency:** Every ADVANCE stock appears only in
   Deep Dive Shortlist. Every WATCHLIST stock appears
   only in Watchlist. No stock appears in both.
4. **Column count:** Full scoring table = exactly 10
   columns. Div? column = only DIVERSIFIER or
   CONCENTRATOR, never a number or JSON value.
5. **Watchlist size:** 5-7 stocks, all scoring above 20.
   Stocks below 20 = ELIMINATED (list tickers only).

---

## Output Format

Plain text. ALL CAPS section titles. Pipe tables.
No markdown. Sections in this order:
```
PRE-OUTPUT CHECKS
-----------------
[5 check results]

DATA AUDIT SUMMARY
------------------
[One paragraph: stocks scored, null counts per field,
fallbacks applied, data quality: HIGH/MEDIUM/LOW]

SCORING LOGIC
-------------
[3 sentences plain English: what each lens tests and
why the weights are set as they are]

FULL SCORING TABLE
------------------
[All stocks, sorted by Total desc]
Ticker | Sector | Rot | Macro | Factor | Quality | Pts | Div? | Total | Notes

COMPOSITE RANKING — TOP 20
---------------------------
[Top 20 only, same columns + Status]
Ticker | Sector | Rot | Macro | Factor | Quality | Pts | Div? | Total | Notes | Status

Final advance list sector distribution:
  Healthcare: X | Energy: X | Staples: X | Utilities: X
  Total advancing: X
Sector cap demotions: [list or NONE]

REASONING CHECK
---------------
A1 (Momentum vs cycle): PASS / [TICKER flagged —
  return_3m X%, rsi X — DEMOTED / RETAINED]
A2 (Leverage vs rates): PASS / [TICKER — debt_to_ebitda X
  — DEMOTED]
A3 (Payout sustainability): PASS / [TICKER — payout X%,
  FCF coverage X — DEMOTED / FLAGGED]
A4 (Valuation vs cycle): PASS / [TICKER — pe_forward X,
  Rot X, Macro X — DEMOTED / RETAINED]
B1 (Sub-industry): PASS / CONCENTRATED IN [industry] —
  [tickers] — noted for Phase 4
B2 (Oil reversal): [TICKER — debt_to_ebitda X — first
  Energy exit if WTI < $75]
B3 (Portfolio beta): Avg beta X — PASS / [TICKER flagged
  for position size reduction]
C1 (Rotation alignment): X% defensive — ALIGNED /
  MISALIGNED
C2 (Energy cap): X Energy stocks — WITHIN CAP / EXCEEDED
  — [action]
C3 (Missing sector): Utilities present YES/NO — [action]

Final advance list after reasoning check:
  [Changes from provisional, or "No changes — confirmed"]

DEEP DIVE SHORTLIST
-------------------
[ADVANCE stocks only, grouped by sector]
[TICKER] — Why advanced: [one sentence, one data point
  with value, connects to cycle thesis]. Risk: [one
  sentence, most important flag from scoring data].

WATCHLIST
---------
[5-7 stocks above score 20, sorted desc]
Ticker | Sector | Total | Why Watchlist

SCORING ANOMALIES
-----------------
[Per stock: anomaly, cause, Phase 4 action: YES/NO/VERIFY]
If none: "No anomalies detected."

ELIMINATED TICKERS
------------------
[Comma-separated, one line]
```

---

## Hard Rules

- Score every stock. No skips. Null = fallback + flag.
- No stock from an avoided sector advances.
- Max 4 stocks per sector in ADVANCE.
- Max 3 Energy stocks in ADVANCE (M2 tactical cap).
- Watchlist = 5-7 stocks, all above score 20.
- Full scoring table = exactly 10 columns.
- Div? column = DIVERSIFIER or CONCENTRATOR only.
- Advance list and Deep Dive Shortlist must be identical.
- Reasoning Check runs before any ADVANCE is confirmed.
- Do not fabricate data. No estimates.