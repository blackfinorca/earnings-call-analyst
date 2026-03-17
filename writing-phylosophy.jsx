const writingPhilosophy = {
  layer: 1,
  id: "WPH",
  name: "Layer 1 Writing Philosophy",
  purpose:
    "This file contains only the Layer 1 writing philosophy used to guide downstream prompts. It is structured to be passed directly into another AI prompt as reference material.",
  coreMandate:
    "Write for a smart generalist who has never read an earnings call or a 10-K. Every investment term, ratio, and concept must be earned — explained before it is used. The reader should finish each section able to repeat the key idea to a friend.",
  principles: [
    {
      id: "WP01",
      name: "Explain Before You Measure",
      rule:
        "Before presenting ANY financial metric, valuation multiple, or ratio, explain what it measures in plain language and why it matters for this investment. Never lead with a number — lead with understanding. A P/E ratio means nothing without first explaining what earnings are and why investors pay more for some than others.",
      examples: {
        fail: "The stock trades at 22x forward P/E vs. a sector median of 18x and a 5-year historical average of 16x. EV/EBITDA is 14x. The PEG ratio of 1.1x suggests the premium is partially justified by growth.",
        pass: "To judge whether a stock is cheap or expensive, investors use a shorthand called the price-to-earnings ratio, or P/E. Think of it as how much you're paying today for each dollar of annual profit. If a company earns $5 per share and the stock costs $100, the P/E is 20 — you're paying $20 for every dollar of earnings. The higher the P/E, the more confidence the market has in future growth. This company trades at 22x earnings — above its own history (16x on average over five years) and above its closest peers (18x). That premium is the first question we need to answer: is it deserved?",
      },
      severity: "CRITICAL",
    },
    {
      id: "WP02",
      name: "One Idea Per Paragraph",
      rule:
        "Each paragraph carries exactly one idea. If a second idea is needed, start a new paragraph. Investment research is especially prone to packing a thesis, supporting data, counterargument, and conclusion into a single dense block. That approach loses every reader. Separate the claim from the evidence from the implication.",
      examples: {
        fail: "Revenue grew 34% YoY to $4.2B with EBIT margins expanding 320bps to 18.4%. FCF conversion improved to 91% vs. 74% last year as capex normalized post-expansion. Net debt fell to 1.2x EBITDA, giving the company flexibility for buybacks or M&A, while the order book grew 22% and management guided for 15-18% organic growth in FY2026.",
        pass: "Revenue grew 34% last year, reaching $4.2 billion. That pace of growth — for a company already this large — is rare and worth examining closely.\n\nProfitability improved alongside revenue. Operating margins expanded from 15% to 18%, meaning the company became more efficient even as it scaled. This matters because many fast-growing companies sacrifice profits to fuel growth.\n\nThe balance sheet also strengthened. Debt fell to a manageable level — just 1.2 times annual operating profit — leaving room for either returning cash to shareholders or making acquisitions.",
      },
      severity: "CRITICAL",
    },
    {
      id: "WP03",
      name: "Analogies Over Acronyms",
      rule:
        "When introducing any investment term, financial concept, or industry-specific language, ALWAYS lead with a real-world analogy. Define every acronym on first use. A reader who encounters DCF, WACC, or ROIC without explanation has already mentally checked out. Give them the idea first, then the label.",
      examples: {
        fail: "Our DCF model uses a WACC of 9.2% and terminal growth rate of 3%, arriving at an intrinsic value of $87/share. ROIC of 24% significantly exceeds WACC, confirming economic value creation.",
        pass: "To estimate what the stock is worth today, we use a method called discounted cash flow analysis — essentially asking: if this business keeps generating cash for the next ten years, and we assume those future dollars are worth slightly less than today's dollars (because a dollar today is more useful than a dollar promised in 2034), what is the business worth right now? Using reasonable assumptions for growth and a cost of capital of about 9% — the return investors could expect from alternatives of similar risk — we arrive at an intrinsic value of roughly $87 per share, about 20% above the current price.\n\nThere's a separate check worth running: is this company actually creating value, or just recycling capital? A metric called return on invested capital (ROIC) measures how much profit the company generates for every dollar it has invested in the business. At 24%, this company earns far more from its investments than it costs to fund them — a hallmark of high-quality compounders.",
      },
      severity: "CRITICAL",
    },
    {
      id: "WP04",
      name: "Thesis First, Evidence Second",
      rule:
        "State the investment thesis — the core claim — at the beginning of every major section, not buried at the end. Readers should never have to infer what you believe. Lead with the conclusion, then build the case. This is the opposite of how academic writing works, and it's the right approach for investment research.",
      examples: {
        fail: "[Section walks through industry dynamics, competitive landscape, financials, and management quality for four pages before concluding: 'For these reasons, we believe the stock represents an attractive long-term opportunity.']",
        pass: "The core thesis is simple: this company has built a pricing advantage that its competitors cannot replicate without losing money, and the market hasn't fully priced that in.\n\nHere's why. [Section then builds the evidence for that specific claim.]",
      },
      severity: "CRITICAL",
    },
    {
      id: "WP05",
      name: "Bull and Bear Cases With Equal Rigor",
      rule:
        "Every investment thesis has a bull case and a bear case. Both must be written with equal intellectual seriousness. A bear case that is two sentences long after a five-page bull case is not a bear case — it's decoration. Readers must be able to understand what would have to be true for this investment to fail.",
      examples: {
        fail: "Risks include macroeconomic headwinds, competitive pressure, and regulatory changes. These are manageable in our view.",
        pass: "The bear case deserves a clear-eyed hearing. The company's growth depends almost entirely on one product category — and that category has never survived a full economic downturn. In the last recession, the sector contracted 40% and two of the three largest players went bankrupt. This company's balance sheet is stronger today, but it carries $3.8 billion in debt that comes due in 2027. If growth slows by even half, refinancing that debt at current rates would wipe out two years of free cash flow. The bull case is compelling — but only if you believe the macro environment stays cooperative for at least 24 more months.",
      },
      severity: "CRITICAL",
    },
    {
      id: "WP06",
      name: "Catalysts, Not Just Conditions",
      rule:
        "A good investment requires not just a compelling valuation or business quality — it requires a reason for the gap between price and value to close. Always identify specific, named catalysts: events, milestones, or disclosures that will force the market to reprice the stock. Vague optimism ('as the business matures') is not a catalyst.",
      examples: {
        fail: "As the market better appreciates the company's competitive position and earnings power, we expect the valuation discount to close over time.",
        pass: "Three specific catalysts could close the gap between today's price and our intrinsic value estimate within 12-18 months:\n\nFirst, the FDA decision on the company's lead drug candidate is expected in Q3 2026. Approval would likely trigger index inclusion, bringing in passive fund flows that currently sit on the sidelines.\n\nSecond, the company is expected to cross $1 billion in annual revenue for the first time in Q2 2026 — a threshold that moves it from 'small-cap speculative' to 'mid-cap growth' in many fund mandates, expanding the institutional buyer base.\n\nThird, the current CEO, who has been associated with a controversial acquisition, is retiring in June. The incoming CEO has a track record of capital discipline that the market tends to reward with multiple expansion.",
      },
      severity: "HIGH",
    },
    {
      id: "WP07",
      name: "Narrative Arc, Not a Checklist",
      rule:
        "The research document must tell a STORY: why this company exists, what changed to create the opportunity, what the market is missing, and what has to happen for the thesis to pay off. Sections must flow into each other — not feel like independent modules from a financial modeling course.",
      examples: {
        fail: "Section 1: Business Overview. Section 2: Industry Analysis. Section 3: Financial Model. Section 4: Valuation. Section 5: Risks. Section 6: Conclusion. [each section is self-contained with no connective tissue]",
        pass: "The research opens by explaining why this industry exists and who it serves -> then identifies the structural shift that has recently changed the rules of competition -> then shows how this company is positioned to benefit from that shift, while its peers are not -> then presents the financial evidence that the shift is already showing up in the numbers -> then asks the honest question: what is the market pricing in, and why might that be wrong -> then stress-tests the thesis against the bear cases -> and closes with a specific, time-bound call on what has to happen for the investment to work.",
      },
      severity: "CRITICAL",
    },
    {
      id: "WP08",
      name: "Human Stakes Over Financial Abstractions",
      rule:
        "Connect financial metrics to real-world consequences wherever possible. 'Operating leverage expanded 400bps' is abstract. 'For every extra $1 of revenue the company earns, 60 cents drops straight to profit because the factory is already paid for' is concrete. Readers remember stories about people and outcomes — not basis points.",
      examples: {
        fail: "The company's high operating leverage profile means incremental revenue growth translates to disproportionate EBIT expansion, driving significant EPS accretion through the cycle.",
        pass: "Here's why the next few years of growth matter so much more than the last few. The company built a manufacturing network that cost $2.4 billion to construct — and that cost is now largely fixed. Whether the factory runs at 60% capacity or 95% capacity, the rent, equipment, and most of the labor costs stay the same. So when revenue grows, the extra money doesn't go back into building more infrastructure — most of it falls straight into profit. A 10% increase in revenue translates to roughly a 25% increase in operating profit. That is an extremely valuable property for investors who believe the company will keep growing.",
      },
      severity: "HIGH",
    },
    {
      id: "WP09",
      name: "Progressive Disclosure",
      rule:
        "Introduce complexity in layers. Begin each section at a level accessible to a curious non-expert, then build toward the nuanced version. Do not front-load every caveat and qualification. The reader should feel like they're gaining clarity, not struggling to keep up. Qualifications belong after the core idea is established.",
      examples: {
        fail: "Adjusting for non-cash stock-based compensation, deferred revenue recognition timing differences, and the impact of the Q3 FY2024 restructuring charge, normalized FCF per share on a diluted basis was $4.12 versus the GAAP-reported ($0.34), representing a significant disconnect that requires careful normalization before meaningful comparison.",
        pass: "The official profit number looks strange this year — the company reports a loss of $0.34 per share. But this is misleading, and understanding why requires a brief detour.\n\nCompanies often report costs in ways that don't reflect actual cash going out the door. Last year, a one-time restructuring charge — the cost of closing two factories and laying off workers — dragged the profit figure into negative territory. Strip that out, and the business generated $4.12 per share in real, spendable cash. That number tells a very different story.",
      },
      severity: "HIGH",
    },
    {
      id: "WP10",
      name: "Comparisons Create Context",
      rule:
        "No number stands alone. Every financial metric must be compared to at least one of: (a) the company's own historical average, (b) direct competitors, or (c) a broader market benchmark. A 30% return on equity is exceptional in utilities and unremarkable in software. Without context, numbers are noise.",
      examples: {
        fail: "Return on equity was 31% in FY2025. Operating margins reached 24%. The stock trades at 19x earnings.",
        pass: "Return on equity was 31% last year — more than double the industry average of 14%, and higher than the company's own five-year average of 22%. This matters: sustained high returns on equity are one of the clearest signals that a business has genuine pricing power, not just favorable market conditions.\n\nOperating margins of 24% place the company in the top quartile of its peer group, where most competitors operate in the 14-18% range. The gap has widened over the last three years — suggesting structural advantage, not a one-time event.\n\nAt 19x earnings, the stock is slightly below its five-year average of 21x, but trades at a premium to the sector median of 16x. The question is whether that premium is justified — and the margin and returns data suggest it probably is.",
      },
      severity: "CRITICAL",
    },
    {
      id: "WP11",
      name: "Time Horizon Is a First-Class Variable",
      rule:
        "Every investment claim must be accompanied by an explicit time horizon. 'This is a great business' and 'this is a great stock to own for the next 12 months' are completely different statements. Mixing them creates confusion. Always specify: over what period does the thesis play out, and why?",
      examples: {
        fail: "Given the strong fundamentals and attractive valuation, we see significant upside for patient investors.",
        pass: "This is a 3-to-5 year investment thesis, not a 12-month trade. The near-term picture is genuinely messy: margins will compress over the next two quarters as the company invests in a new distribution network, and the stock may drift lower or sideways during that period.\n\nBut by FY2027, that investment should begin generating returns. The new distribution footprint will allow the company to serve a customer segment it currently cannot reach — representing roughly $800 million in addressable revenue it is leaving on the table today. Investors who need a catalyst in the next six months should look elsewhere. Investors with a longer horizon are being offered the chance to buy a franchise business at a non-franchise price.",
      },
      severity: "HIGH",
    },
    {
      id: "WP12",
      name: "White Space Is a Feature",
      rule:
        "Short paragraphs, breathing room between ideas, and deliberate pacing are not wasted space — they are comprehension tools. Financial research is already cognitively demanding. Dense text compounds that burden. A 20-page report the reader finishes is worth more than a 40-page report they abandon halfway through.",
      examples: {
        fail: "[Wall of text with 8+ sentences per paragraph, financials embedded in prose, no visual breaks, no callout boxes for key numbers, no transition sentences between sections]",
        pass: "[Paragraphs of 2-4 sentences. Key metrics in their own callout blocks. Transition sentences that tell the reader what section they're entering and why it follows logically from what came before. Bear case in its own clearly labeled subsection. Each catalyst numbered and separated.]",
      },
      severity: "HIGH",
    },
    {
      id: "WP13",
      name: "The Dinner Table Test",
      rule:
        "Every section should pass this test: 'Could I explain this to a smart friend over dinner — without a whiteboard, without jargon, without losing their attention?' If you couldn't, rewrite it. The goal is not to impress with complexity. The goal is to transfer understanding.",
      examples: {
        fail: "The company's asymmetric risk/reward profile, combined with near-trough EV/EBITDA multiples and inflecting ROIC trajectory, suggests a favorable risk-adjusted entry point for long-biased investors with a 12-18 month investment horizon.",
        pass: "Here's the simple version: the stock is cheap relative to what the business earns, the business is getting more profitable every year, and the main thing holding the stock price back — uncertainty around a regulatory decision — resolves in the next six months. If the decision goes well, the stock re-rates. If it doesn't, the downside is cushioned by the fact that the underlying business is still healthy and growing.",
      },
      severity: "CRITICAL",
    },
  ],
};

export default writingPhilosophy;
