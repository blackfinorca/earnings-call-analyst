## Universe Generation Prompt (M3a)

### Runtime Context

Input files:

- `M2 Sector ranking/sector-ranking-report.md` — primary source. Read
  every section before running a single search. The M3a Search Brief
  section at the bottom of M2 contains your sector stock counts,
  sub-industry targeting, stock characteristics, and catalyst types.
  These are mandatory inputs, not optional context.
- `M1 macro scan/research-macro-scan.json` — supporting source for
  raw macro data. Use only if M2 references a data point that needs
  grounding in the original numbers.

Return the final result as a JSON code block to
`M3A Universe generation/universe-generation.json`.

---

### Your Job

Generate a universe of 30-50 real, investable US-listed stocks from
the favored sectors identified in M2. Every stock in this universe
will be passed to an external API to collect standardized
fundamentals. The API step is the quality gate — your job is to
produce a broad, well-targeted candidate list, not a pre-screened
shortlist. Include borderline candidates and mark them UNVERIFIED
rather than leaving gaps.

---

### Step 1 — Read M2 Before Searching

Before running any search, read these M2 sections in order:

1. **Consolidated Sector Priority** — identifies Overweight, Neutral,
   and Underweight tiers. You will only generate stocks from Overweight
   sectors. Do not include stocks from Neutral or Underweight sectors
   unless a specific exception is noted in M2.

2. **M3a Search Brief** — contains:
   - Target stock count per sector (use these as your search targets)
   - Six stock characteristics to prioritize (use these to build
     targeted search queries, not generic sector searches)
   - Catalyst types to scan for in the next 30-90 days
   - Sectors to exclude with any partial exceptions noted

3. **Macro Themes** — read the Portfolio Implication and sub-industry
   guidance in each theme. These tell you which sub-industries within
   each sector to prioritize and which to avoid.

Do not begin searching until you have read all three sections.

---

### Step 2 — Build Targeted Search Queries

For each favored sector, construct queries using the sub-industry
guidance and stock characteristics from M2 — not generic sector
labels. The goal is to surface specific, cycle-aligned names that
generic searches would miss.

**Query construction rules:**

- Every query must include at least one sub-industry term from M2's
  portfolio implications (e.g., "integrated oil major refining" not
  just "energy stocks")
- At least one query per sector must reference a specific stock
  characteristic from M2's Search Brief (e.g., "gross margin above
  40%" or "subscription revenue model")
- At least one query per sector must reference a current catalyst
  type (e.g., "FDA approval 2026" or "utility rate case decision")
- Do not repeat the same query structure across sectors

**Example of wrong query approach:**
- "best healthcare stocks 2026"
- "top healthcare stocks by market cap"
- "analyst picks healthcare sector"

**Example of right query approach (Healthcare in a stagflation
cycle):**
- "large cap pharmaceutical patent-protected drugs pricing power
  analyst buy 2026"
- "pharmaceutical company gross margin above 40 percent EPS growth
  2026"
- "FDA approval catalyst Q2 2026 pharmaceutical"
- "medical device company recurring revenue switching costs 2026"

**Search budget allocation:**

Read the M2 Search Brief sector stock counts. Allocate searches
proportionally to target count. As a guide:

- Sectors targeting 12-15 stocks: 5 searches
- Sectors targeting 8-10 stocks: 3-4 searches
- Sectors targeting 6-8 stocks: 3 searches
- Reserve 2-3 searches for cross-sector validation, gap-filling,
  or confirming uncertain candidates

Total search budget: 20 searches. Plan your allocation before
running the first query.

---

### Step 3 — Candidate Collection Rules

For each search result, apply this decision process:

**Include and mark VERIFIED if all of the following are true:**
- US-listed common stock on NYSE or Nasdaq
- Market cap clearly above $2 billion
- Company is profitable (any indication of positive earnings)
- Not an ETF, closed-end fund, SPAC, ADR, or IPO within 24 months
- Operates in a favored sector (not an avoid sector)

**Include and mark UNVERIFIED if:**
- The stock likely meets filters but you cannot confirm one or more
  (e.g., market cap is unclear, profitability uncertain)
- The stock is a strong thematic fit but you lack enough data to
  confirm all filters
- The company name suggests it belongs in a favored sector but
  sector classification is ambiguous

**Exclude entirely if:**
- The stock is in an explicitly avoided sector with no noted exception
- It is clearly an ETF, SPAC, foreign-listed stock, or recent IPO
- It is a meme stock or has no institutional analyst coverage

**Never exclude a candidate just because you are uncertain.** The API
step will confirm or remove unverified names. A false inclusion costs
nothing. A false exclusion removes a potentially strong candidate
permanently.

---

### Step 4 — why_included Quality Standard

The `why_included` field is read by M3b to pre-score candidates
before API data arrives. It must connect the stock to the current
cycle, not just describe what the company does.

**Acceptable:** "Integrated oil major with domestic refining
operations — direct beneficiary of $95 oil spike per M2 Energy
thesis; low debt-to-EBITDA supports inflation-hedge positioning."

**Not acceptable:** "Large energy company with analyst buy rating."
"Well-known healthcare stock." "Strong earnings growth."

Each `why_included` must reference at least one of:
- A named M2 sector thesis or macro theme
- A specific stock characteristic from the M2 Search Brief
  (e.g., gross margin, debt level, revenue model)
- A named catalyst type from the M2 Search Brief

One sentence maximum. Be specific, not descriptive.

---

### Step 5 — Sector Distribution and Quality Check

Before finalizing output, run this check:

1. Count stocks per sector. Compare to M2 Search Brief target counts.
   If any sector is more than 3 stocks below target, run one
   additional search for that sector before outputting.

2. Count UNVERIFIED stocks. If more than 30% of the universe is
   UNVERIFIED, note it in the `quality_flags` field.

3. Check for duplicate tickers. Remove any duplicates, keeping the
   entry with the more specific `why_included`.

4. Check that no stock from an avoid sector has been included.
   If found, remove it.

5. Confirm total count is between 30 and 50. If below 30, run
   additional searches. If above 50, remove the weakest UNVERIFIED
   candidates until count is 50 or below.

---

### Output Format

Output a single JSON code block. No text before or after it.
```json
{
  "cycle_date": "YYYY-MM-DD",
  "rotation_score": -1,
  "rotation_score_range": "-1 confirmed, plausibly -3 if missing triggers resolve defensive",
  "cycle_phase": "Late Cycle / Stagflation",
  "favored_sectors": [
    {
      "name": "Healthcare",
      "etf": "XLV",
      "rank": 1,
      "thesis": "One sentence from M2 Consolidated Sector Priority",
      "target_count": 13,
      "sub_industries_prioritized": ["large-cap pharma", "medical devices"],
      "sub_industries_avoided": ["hospitals", "insurers"]
    }
  ],
  "avoid_sectors": [
    {
      "name": "Financials",
      "etf": "XLF",
      "reason": "One sentence from M2"
    }
  ],
  "macro_themes": [
    "Theme statement from M2 — one sentence each"
  ],
  "universe": [
    {
      "ticker": "LLY",
      "company": "Eli Lilly and Company",
      "sector": "Healthcare",
      "sector_rank": 1,
      "sub_industry": "Pharmaceuticals",
      "why_included": "Patent-protected GLP-1 drug franchise with pricing power above inflation; gross margin above 70%; FDA catalyst pipeline active in 2026 per M2 Healthcare thesis.",
      "verified": true
    },
    {
      "ticker": "EXAMPLE",
      "company": "Example Corp",
      "sector": "Utilities",
      "sector_rank": 2,
      "sub_industry": "Regulated Electric",
      "why_included": "Regulated rate structure with approved inflation pass-through; rate case decision expected Q2 2026 per M2 catalyst list; debt-to-EBITDA below 1.5x.",
      "verified": false
    }
  ],
  "total_count": 38,
  "sector_distribution": {
    "Healthcare": 13,
    "Utilities": 9,
    "Consumer Staples": 9,
    "Energy": 7
  },
  "search_log": [
    {
      "query": "large cap pharmaceutical patent pricing power analyst buy 2026",
      "sector": "Healthcare",
      "tickers_surfaced": ["LLY", "ABBV", "MRK", "BMY"]
    }
  ],
  "quality_flags": [
    "Utilities universe is 2 stocks below target — insufficient results for 4th search query",
    "3 of 38 stocks are UNVERIFIED due to uncertain profitability"
  ]
}
```

---

### Hard Rules Summary

- Output only the JSON code block. No prose before or after.
- Every ticker maps to exactly one favored sector.
- No ETFs, SPACs, ADRs, foreign-listed stocks, or IPOs under 24 months.
- No stocks from avoid sectors unless M2 explicitly noted an exception.
- No duplicate tickers.
- `why_included` must reference M2 thesis, characteristic, or catalyst — not just describe the company.
- Target 30-50 stocks. 35 accurate names beats 50 with 15 generic ones.
- If a favored sector yields fewer than its target count after all searches, note it in `quality_flags` and do not pad with weak candidates.
- `search_log` is required. Every search run must appear in it.