## Sector Ranking Output Prompt

### Runtime Context

Input files:

- `M1 macro scan/research-macro-scan.json` — source of truth for all market and macro data. Read the top-level `rows` array, ignore `provider_outputs`. Flag derived rows when cited. Flag any row with `source.as_of` older than two weeks as stale.
- `writing-philosophy.jsx` — binding writing standard. Apply it to every section.

Return the result as markdown to `M2 Sector ranking/sector-ranking-report.md`. No JSON. No code fences.

---

### Section 1 — Market Snapshot

Write one headline sentence capturing the market's current character as a judgment call, not a data summary.

Write 3 to 5 key takeaways. Each is one sentence: one condition, one implication. Define any technical term inline on first use — one clause is enough.

Then present the dashboard table: `Data Point | Current Value | Prior Reading | Direction (↑↓→) | Signal Implication | Status | Stale`

Status options: `confirmed` (live data this session), `derived` (calculated — say how), `unavailable`. Stale format: `Stale (as of YYYY-MM-DD)`. Do not skip rows.

---

### Section 2 — Economic Cycle Positioning

Open with two sentences. First: the cycle phase. Second: the growth-inflation quadrant. No hedging.

**Cycle phases:** Early Expansion | Mid-Cycle | Late Cycle | Contraction/Recession

**Growth-inflation quadrants:** Rising Growth + Rising Inflation | Rising Growth + Falling Inflation | Falling Growth + Rising Inflation (Stagflation) | Falling Growth + Falling Inflation (Deflation Risk)

Write 3 to 5 reasoning sentences, each naming a specific data point from Section 1 with its value. No general statements.

**Jargon rule:** The first time any of these terms appear — stagflation, yield curve, basis points, PCE, PMI, annualized — define it in plain English in the same sentence or the one immediately after. One sentence is enough.

**Consistency check:** State in one sentence whether the cycle verdict and the Section 3 scorecard point in the same direction. If they conflict, explain why before closing this section.

Close with: `Cycle Phase | Favored Sector Categories | Disfavored Sector Categories`

---

### Section 3 — Sector Rotation Trigger Scorecard

Score five triggers. Table: `Trigger | Current Data (2-4 values) | Score | Reasoning (1-2 sentences)`

**Scoring rules:**

| Trigger | +1 (Cyclical) | 0 (Neutral) | -1 (Defensive) |
|---|---|---|---|
| Interest Rates | Fed cutting or dovish pivot signaled | Fed on hold, no directional signal | Fed hiking or hawkish |
| Economic Data | PMI > 50 AND accelerating vs. 3-month avg | PMI near 50 or mixed | PMI < 50 AND decelerating |
| Earnings Revisions | Growth sector upgrades outnumber downgrades | Mixed or data insufficient | Downgrades dominate |
| Commodity Prices | Oil AND copper both rising | Flat or diverging | Oil AND copper both falling |
| Consumer Spending | Retail sales positive, confidence rising | Flat or mixed | Retail sales declining, confidence falling |

**Commodity context rule:** If oil is rising, state whether this reflects demand strength (cyclical signal) or supply disruption (inflationary headwind). Score reflects whichever interpretation is better supported by the growth data.

**Missing data rule:** If a trigger cannot be scored, mark it 0 and write: "Scored 0 by default — data unavailable. This score is not analytical." After the table, state how many triggers defaulted and what the score would be under the most plausible assumption for each.

Add a summary row: `Net Score | — | [sum] | [label]`

Interpretation thresholds:
- ≥ +3: Strong Cyclical Lean — overweight Industrials, Materials, Discretionary, Financials
- +1 to +2: Mild Cyclical Lean — slight overweight cyclicals, maintain diversification
- 0: Neutral — no sector edge; focus on stock selection
- -1 to -2: Mild Defensive Lean — slight overweight Healthcare, Staples, Utilities
- ≤ -3: Strong Defensive Lean — overweight Utilities, Healthcare, Staples

Write one positioning paragraph (3 to 5 sentences). Lead with the two specific catalysts that would shift the score. Then state current positioning. Name sectors explicitly. Do not open with "the scorecard reveals."

**Then close Section 3 with this block — it is required and feeds directly into M3a:**

#### Consolidated Sector Priority

Rank all 11 GICS sectors into three tiers based on the cycle verdict and scorecard combined. Use the sector ETF tickers as reference labels. One sentence of reasoning per tier.

| Tier | Sectors (ranked within tier) | Rationale |
|---|---|---|
| Overweight (1-3 sectors) | [ranked list] | [one sentence] |
| Neutral (4-7 sectors) | [ranked list] | [one sentence] |
| Underweight (8-11 sectors) | [ranked list] | [one sentence] |

If any sector has a split signal — favored by one theme but disfavored by another — note it explicitly with a one-line exception. M3a will use this table as its primary sector allocation guide.

---

### Section 4 — Macro Themes

Identify 3 to 5 dominant themes. Each must be specific enough that a colleague could disagree with it. Generic observations are not themes.

For each theme write five components in this order:

**Theme Statement** — one sentence: the force, its direction, its scope.

**Thesis** — 2 to 4 sentences of economic logic. Why is this happening? What sustains it? Connect cause to effect.

**Human stakes** — 1 to 2 sentences. Translate the theme into a concrete consequence for a specific type of business, worker, or consumer. Name them. Do not write for investors — write about the real-world actors the theme affects. This is what makes the theme tangible before the portfolio implication.

**Evidence** — 2 to 4 specific data points or recent events with dates and values.

**Portfolio implication** — 2 to 3 sentences. Name what to buy and what to avoid. Then add one sentence of stock-type specificity: name the sub-industry, business model, or company characteristic M3a should search for within the favored sector. Example: "Within Energy, prioritize integrated majors with domestic refining exposure over pure-play E&P names — refiners capture the margin between crude input costs and refined product prices, which widens when oil spikes."

Web search is permitted here for Fed commentary, geopolitical developments, earnings revisions context, and theme validation. Use as supplementary evidence, not a substitute for macro scan data.

---

### Section 5 — M3a Search Brief

This section is written entirely for machine consumption. It will be read by the M3a phase (11-sector scoring and 30-50 stock universe generation) as its primary instruction set. Write it as a structured brief, not prose.
This section is mandatory and must not be truncated. If length pressure requires cuts elsewhere, reduce the Evidence bullets in Macro Themes to two points each before shortening this section.

**Sector allocation for universe generation:**
List the Overweight sectors from the Consolidated Sector Priority block. For each, state the target number of candidate stocks to generate (total universe should be 30-50 stocks across all favored sectors).

**Stock characteristics to prioritize across all sectors:**
List 4 to 6 specific, screenable characteristics that reflect the current cycle and themes. Examples of the right level of specificity: "pricing power demonstrated by gross margins above 40%," "domestic revenue concentration above 60% (reduces currency and trade policy risk)," "debt-to-equity below 1.0 (insulates from rising rate pressure)." Do not list generic quality factors — anchor each characteristic to a current macro condition.

**Catalyst types to scan for (next 30-90 days):**
List 3 to 5 specific catalyst categories relevant to this cycle's themes. Examples: earnings dates for companies in favored sectors, Fed meeting dates and their implications, commodity price inflection points, regulatory decisions, index rebalancing dates.

**Hard filters — apply before any other screen:**
- US-listed only
- Market cap above $2 billion
- Profitable (positive trailing twelve-month earnings)
- Average daily volume above $5 million
- Not a SPAC, meme stock, or IPO within the last 24 months

**Sectors to exclude from search:**
List the Underweight sectors from the Consolidated Sector Priority block. Note any partial exceptions (e.g., "exclude Financials broadly, but regional banks with significant fixed-rate loan books may be screened separately if the yield curve steepens").

**Score uncertainty note:**
If any triggers in Section 3 were data-defaulted, state the plausible score range here (e.g., "scorecard is -2 confirmed; could be -3 if earnings revisions and retail sales data confirm the defensive lean — M3a should weight defensives accordingly and treat cyclical candidates with additional scrutiny").

---

### Section 6 — Data Sources and Research Log

Structured list only:

- Macro scan generation timestamp
- Data providers used
- Derived data points with formula or logic used
- Stale data points with date of last available reading
- Topics where web search was used
- Data points unavailable and how they were handled

---

### Output Section Order
```
# Sector Ranking
Input File: M1 macro scan/research-macro-scan.json
Generated At: [ISO-8601]

## Market Snapshot
## Economic Cycle Positioning
## Sector Rotation Trigger Scorecard
### Consolidated Sector Priority
## Macro Themes
## M3a Search Brief
## Data Sources and Research Log
```