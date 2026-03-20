#!/usr/bin/env python3
"""document-builder.py — Assembles a formatted Word report from pipeline output files.

Usage:
    python document-builder.py
    python document-builder.py --output report.docx

Reads (all optional — missing files produce a placeholder section):
    M1 macro scan/research-macro-scan.json
    M2 Sector ranking/sector-ranking-report.md
    M3A Universe generation/universe-generation.json
    M3B stock screening/stock-screener.txt
    M5 Portfolio construction/portfolio-construction-output.md

Writes:
    investment-strategy-report-YYYY-MM-DD.docx  (or --output path)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor
except ModuleNotFoundError:
    sys.exit(
        "python-docx is not installed.\n"
        "Run: .venv/bin/pip install python-docx"
    )

BASE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Input paths
# ---------------------------------------------------------------------------

M1_PATH  = BASE_DIR / "M1 macro scan"            / "research-macro-scan.json"
M2_PATH  = BASE_DIR / "M2 Sector ranking"         / "sector-ranking-report.md"
M3U_PATH = BASE_DIR / "M3A Universe generation"   / "universe-generation.json"
M3B_PATH = BASE_DIR / "M3B stock screening"       / "stock-screener.txt"
M5_PATH  = BASE_DIR / "M5 Portfolio construction" / "portfolio-construction-output.md"

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------

NAVY       = RGBColor(0x1A, 0x27, 0x44)
NAVY_LIGHT = RGBColor(0x2E, 0x3F, 0x6A)
GOLD       = RGBColor(0xC9, 0xA8, 0x4C)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
OFFWHITE   = RGBColor(0xF7, 0xF8, 0xFA)
LIGHT_GREY = RGBColor(0xEE, 0xF0, 0xF3)
MID_GREY   = RGBColor(0xAA, 0xAA, 0xAA)
DARK_GREY  = RGBColor(0x55, 0x55, 0x55)

SIG_BUY    = RGBColor(0xC6, 0xEF, 0xCE)
SIG_HOLD   = RGBColor(0xFF, 0xEB, 0x9C)
SIG_WATCH  = RGBColor(0xFF, 0xC7, 0x77)
SIG_SKIP   = RGBColor(0xFF, 0xC7, 0xCE)

SIG_BUY_TXT   = RGBColor(0x27, 0x6A, 0x35)
SIG_HOLD_TXT  = RGBColor(0x7D, 0x6B, 0x00)
SIG_WATCH_TXT = RGBColor(0x8B, 0x4A, 0x00)
SIG_SKIP_TXT  = RGBColor(0x9C, 0x00, 0x06)

ADV_COLOR  = RGBColor(0xC6, 0xEF, 0xCE)
WTCH_COLOR = RGBColor(0xFF, 0xEB, 0x9C)
ELIM_COLOR = RGBColor(0xFF, 0xC7, 0xCE)


def _hex(rgb: RGBColor) -> str:
    return str(rgb).upper()


# ---------------------------------------------------------------------------
# Low-level XML helpers
# ---------------------------------------------------------------------------

def set_cell_bg(cell, rgb: RGBColor) -> None:
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  _hex(rgb))
    tcPr.append(shd)


def set_cell_width(cell, inches: float) -> None:
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcW  = OxmlElement("w:tcW")
    tcW.set(qn("w:w"),    str(int(inches * 1440)))
    tcW.set(qn("w:type"), "dxa")
    tcPr.append(tcW)


def cell_font(cell, *, bold: bool = False, size: int = 9,
              color: RGBColor | None = None, italic: bool = False,
              align: WD_ALIGN_PARAGRAPH = WD_ALIGN_PARAGRAPH.LEFT) -> None:
    for para in cell.paragraphs:
        para.alignment = align
        for run in para.runs:
            run.bold        = bold
            run.italic      = italic
            run.font.size   = Pt(size)
            run.font.name   = "Calibri"
            if color:
                run.font.color.rgb = color


def add_borders(table, color: str = "CCCCCC", sz: str = "4") -> None:
    for tr in table._tbl.findall(qn("w:tr")):
        for tc in tr.findall(qn("w:tc")):
            tcPr = tc.find(qn("w:tcPr"))
            if tcPr is None:
                tcPr = OxmlElement("w:tcPr")
                tc.insert(0, tcPr)
            tcBorders = OxmlElement("w:tcBorders")
            for side in ("top", "left", "bottom", "right"):
                b = OxmlElement(f"w:{side}")
                b.set(qn("w:val"),   "single")
                b.set(qn("w:sz"),    sz)
                b.set(qn("w:space"), "0")
                b.set(qn("w:color"), color)
                tcBorders.append(b)
            tcPr.append(tcBorders)


def style_header_row(row, bg: RGBColor = NAVY,
                     text_color: RGBColor = WHITE,
                     font_size: int = 9) -> None:
    for cell in row.cells:
        set_cell_bg(cell, bg)
        cell_font(cell, bold=True, size=font_size, color=text_color,
                  align=WD_ALIGN_PARAGRAPH.CENTER)


# ---------------------------------------------------------------------------
# Document structure helpers
# ---------------------------------------------------------------------------

def _gold_rule(doc: Document, before: int = 0, after: int = 6) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after  = Pt(after)
    pPr  = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bot  = OxmlElement("w:bottom")
    bot.set(qn("w:val"),   "single")
    bot.set(qn("w:sz"),    "8")
    bot.set(qn("w:space"), "1")
    bot.set(qn("w:color"), _hex(GOLD))
    pBdr.append(bot)
    pPr.append(pBdr)


_section_counter = 0


def _next_section_num() -> str:
    global _section_counter
    _section_counter += 1
    return f"{_section_counter:02d}"


def add_section_heading(doc: Document, text: str) -> None:
    num = _next_section_num()
    p   = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(24)
    p.paragraph_format.space_after  = Pt(2)
    # Section number in gold
    r_num = p.add_run(f"{num}  ")
    r_num.bold           = True
    r_num.font.size      = Pt(18)
    r_num.font.name      = "Calibri"
    r_num.font.color.rgb = GOLD
    # Section title in navy
    r_txt = p.add_run(text.upper())
    r_txt.bold           = True
    r_txt.font.size      = Pt(18)
    r_txt.font.name      = "Calibri"
    r_txt.font.color.rgb = NAVY
    _gold_rule(doc, before=2, after=8)


def add_h2(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after  = Pt(4)
    r = p.add_run(text)
    r.bold           = True
    r.font.size      = Pt(12)
    r.font.name      = "Calibri"
    r.font.color.rgb = NAVY


def add_h3(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after  = Pt(2)
    r = p.add_run(text)
    r.bold           = True
    r.italic         = True
    r.font.size      = Pt(10)
    r.font.name      = "Calibri"
    r.font.color.rgb = NAVY_LIGHT


def add_body(doc: Document, text: str, size: int = 10, color: RGBColor | None = None) -> None:
    p = doc.add_paragraph()
    p.style = "Normal"
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.font.name = "Calibri"
    if color:
        r.font.color.rgb = color


def add_note(doc: Document, text: str) -> None:
    add_body(doc, f"  {text}", size=8, color=MID_GREY)


def add_bullet(doc: Document, text: str, size: int = 9) -> None:
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.font.name = "Calibri"


def add_spacer(doc: Document, pts: int = 6) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = Pt(pts)


def _add_page_field(para) -> None:
    """Append an auto PAGE field to a paragraph."""
    for tag, text in [("begin", None), ("instrText", "PAGE"), ("end", None)]:
        run  = para.add_run()
        elem = OxmlElement("w:fldChar" if tag != "instrText" else "w:instrText")
        if tag == "instrText":
            elem.text = text
            run._r.append(elem)
        else:
            elem.set(qn("w:fldCharType"), tag)
            run._r.append(elem)


def add_footer(doc: Document, report_date: str) -> None:
    for section in doc.sections:
        section.footer_distance = Inches(0.4)
        footer = section.footer
        # Clear any existing content
        for p in footer.paragraphs:
            p.clear()
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        # Left side: company + report date
        r_left = fp.add_run(f"Blackfin Orca  ·  Investment Strategy Research  ·  {report_date}    Page ")
        r_left.font.size = Pt(8)
        r_left.font.name = "Calibri"
        r_left.font.color.rgb = MID_GREY
        _add_page_field(fp)
        # Top border on footer
        pPr  = fp._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        top  = OxmlElement("w:top")
        top.set(qn("w:val"),   "single")
        top.set(qn("w:sz"),    "4")
        top.set(qn("w:space"), "3")
        top.set(qn("w:color"), _hex(LIGHT_GREY))
        pBdr.append(top)
        pPr.append(pBdr)


# ---------------------------------------------------------------------------
# Table builder
# ---------------------------------------------------------------------------

def parse_pipe_table(text: str) -> list[list[str]]:
    """Parse pipe-separated rows.  Handles both |val|val| and val | val formats."""
    rows: list[list[str]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or "|" not in s:
            continue
        # Separator row (---|---|...)
        if re.match(r"^[\s\-:|]+$", s.replace("|", "")):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if any(cells):
            rows.append(cells)
    return rows


def make_table(doc: Document, rows: list[list[str]], *,
               header_bg: RGBColor = NAVY,
               font_size: int = 9,
               col_widths: list[float] | None = None,
               row_colors: dict[int, RGBColor] | None = None,
               center_from: int = 1) -> None:
    """Render a list-of-rows as a formatted Word table and add it to doc."""
    if not rows:
        return

    ncols = max(len(r) for r in rows)
    rows  = [r + [""] * (ncols - len(r)) for r in rows]

    tbl = doc.add_table(rows=len(rows), cols=ncols)
    tbl.style     = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT

    for i, row in enumerate(rows):
        for j, txt in enumerate(row):
            cell = tbl.rows[i].cells[j]
            cell.text = txt
            align = (WD_ALIGN_PARAGRAPH.CENTER
                     if j >= center_from else WD_ALIGN_PARAGRAPH.LEFT)
            cell_font(cell, size=font_size, align=align)
            if col_widths and j < len(col_widths):
                set_cell_width(cell, col_widths[j])

        if i == 0:
            style_header_row(tbl.rows[0], bg=header_bg, font_size=font_size)
        else:
            if row_colors and i in row_colors:
                for cell in tbl.rows[i].cells:
                    set_cell_bg(cell, row_colors[i])
            elif i % 2 == 0:
                for cell in tbl.rows[i].cells:
                    set_cell_bg(cell, LIGHT_GREY)

    add_borders(tbl)
    add_spacer(doc, 8)


def add_color_legend(doc: Document,
                     items: list[tuple[str, RGBColor, RGBColor]]) -> None:
    """items = [(label, bg_color, text_color), ...]"""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    r0 = p.add_run("Legend:  ")
    r0.bold        = True
    r0.font.size   = Pt(8)
    r0.font.name   = "Calibri"
    r0.font.color.rgb = DARK_GREY
    for label, _, txt_color in items:
        r = p.add_run(f"  ■ {label}  ")
        r.bold           = True
        r.font.size      = Pt(8)
        r.font.name      = "Calibri"
        r.font.color.rgb = txt_color


# ---------------------------------------------------------------------------
# Markdown body renderer (for M2)
# ---------------------------------------------------------------------------

def render_md_body(doc: Document, text: str, font_size: int = 9) -> None:
    lines     = text.splitlines()
    tbl_buf: list[str] = []
    in_table  = False

    def flush_tbl():
        nonlocal tbl_buf, in_table
        rows = parse_pipe_table("\n".join(tbl_buf))
        if rows:
            make_table(doc, rows, font_size=font_size - 1)
        tbl_buf = []
        in_table = False

    for line in lines:
        s = line.strip()

        # Table line detection
        if "|" in s and (s.startswith("|") or re.match(r"^\w.*\|", s)):
            in_table = True
            tbl_buf.append(line)
            continue
        else:
            if in_table:
                flush_tbl()

        if not s:
            continue

        if re.match(r"^#{3} ", s):
            add_h3(doc, s[4:])
        elif re.match(r"^#{1,2} ", s):
            add_h2(doc, re.sub(r"^#+\s*", "", s))
        elif re.match(r"^\*\*[^*]+\*\*:?\s*$", s):
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run(s.strip("*").rstrip(":"))
            r.bold           = True
            r.font.size      = Pt(font_size)
            r.font.name      = "Calibri"
            r.font.color.rgb = NAVY
        elif s.startswith(("- ", "* ")):
            add_bullet(doc, s[2:], size=font_size - 1)
        else:
            clean = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
            clean = re.sub(r"\*(.+?)\*",     r"\1", clean)
            add_body(doc, clean, size=font_size)

    if in_table:
        flush_tbl()


# ---------------------------------------------------------------------------
# Cover page
# ---------------------------------------------------------------------------

def section_cover(doc: Document, run_date: str, m1_meta: dict | None) -> None:
    # --- Top spacer
    for _ in range(6):
        add_spacer(doc, 4)

    # --- Main title
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("INVESTMENT STRATEGY RESEARCH")
    r.bold           = True
    r.font.size      = Pt(30)
    r.font.name      = "Calibri"
    r.font.color.rgb = NAVY

    # --- Gold rule under title
    _gold_rule(doc, before=4, after=8)

    # --- Subtitle
    s = doc.add_paragraph()
    s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = s.add_run("Blackfin Orca  ·  Systematic Equity Research")
    r2.font.size      = Pt(14)
    r2.font.name      = "Calibri"
    r2.font.color.rgb = GOLD

    add_spacer(doc, 24)

    # --- Date
    dp = doc.add_paragraph()
    dp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r3 = dp.add_run(f"Report Date:  {run_date}")
    r3.font.size      = Pt(12)
    r3.font.name      = "Calibri"
    r3.font.color.rgb = DARK_GREY

    # --- Data provenance
    if m1_meta:
        gen_at = m1_meta.get("generated_at", "")[:19].replace("T", " ")
        prov   = "  ·  ".join(m1_meta.get("providers", []))

        sp = doc.add_paragraph()
        sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r4 = sp.add_run(f"Data as of  {gen_at}")
        r4.font.size      = Pt(10)
        r4.font.name      = "Calibri"
        r4.font.color.rgb = MID_GREY

        pp = doc.add_paragraph()
        pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r5 = pp.add_run(f"Sources:  {prov}")
        r5.font.size      = Pt(9)
        r5.font.name      = "Calibri"
        r5.font.color.rgb = MID_GREY

    add_spacer(doc, 32)

    # --- Table of contents summary
    toc = doc.add_paragraph()
    toc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r6 = toc.add_run("CONTENTS")
    r6.bold           = True
    r6.font.size      = Pt(10)
    r6.font.name      = "Calibri"
    r6.font.color.rgb = NAVY

    _gold_rule(doc, before=2, after=6)

    sections = [
        ("01", "Macro Environment",    "Market dashboard, yield curve, cycle phase"),
        ("02", "Sector Ranking",        "Rotation scorecard, favoured sectors, thematic rationale"),
        ("03", "Investment Universe",   "Macro themes, screened universe, sector allocation"),
        ("04", "Stock Screening",       "Multi-lens scoring, composite ranking, advance list"),
        ("05", "Portfolio Construction","16-category scoring, portfolio allocation, recommendations"),
    ]
    for num, title, desc in sections:
        row_p = doc.add_paragraph()
        row_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        row_p.paragraph_format.space_after = Pt(3)
        rn = row_p.add_run(f"{num}  ")
        rn.bold           = True
        rn.font.size      = Pt(10)
        rn.font.name      = "Calibri"
        rn.font.color.rgb = GOLD
        rt = row_p.add_run(f"{title:<26}")
        rt.bold           = True
        rt.font.size      = Pt(10)
        rt.font.name      = "Calibri"
        rt.font.color.rgb = NAVY
        rd = row_p.add_run(f"  {desc}")
        rd.font.size      = Pt(9)
        rd.font.name      = "Calibri"
        rd.font.color.rgb = DARK_GREY

    add_spacer(doc, 16)
    _gold_rule(doc, before=0, after=4)

    conf = doc.add_paragraph()
    conf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rc = conf.add_run("CONFIDENTIAL  ·  Internal Use Only  ·  Not for Distribution")
    rc.italic         = True
    rc.font.size      = Pt(8)
    rc.font.name      = "Calibri"
    rc.font.color.rgb = MID_GREY

    doc.add_page_break()


# ---------------------------------------------------------------------------
# M1 — Macro Environment
# ---------------------------------------------------------------------------

def section_m1(doc: Document, path: Path) -> None:
    add_section_heading(doc, "Macro Environment")

    if not path.exists():
        add_note(doc, f"File not found: {path.name}")
        return

    data   = json.loads(path.read_text())
    rows   = data.get("rows", [])
    gen_at = data.get("generated_at", "")[:19].replace("T", " ")
    add_note(doc, f"Generated: {gen_at}  ·  Sources: {', '.join(data.get('providers', []))}")

    add_h2(doc, "Market Dashboard")

    ARROWS = {"up": "↑", "down": "↓", "flat": "→", "stable": "→", "unchanged": "→"}
    DIR_COLOR = {"up": SIG_BUY_TXT, "down": SIG_SKIP_TXT, "flat": DARK_GREY}

    headers  = ["Data Point", "Current", "Prior", "Dir", "Signal Implication", "Status"]
    widths   = [1.5, 0.9, 0.9, 0.4, 3.2, 0.8]
    tbl      = doc.add_table(rows=1 + len(rows), cols=len(headers))
    tbl.style     = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT

    # Header row
    for j, (h, w) in enumerate(zip(headers, widths)):
        cell = tbl.rows[0].cells[j]
        cell.text = h
        set_cell_width(cell, w)
    style_header_row(tbl.rows[0], font_size=8)

    for i, row in enumerate(rows, 1):
        status  = row.get("status", "")
        unavail = status == "unavailable"
        direction = row.get("direction", "")
        cells = tbl.rows[i].cells
        values = [
            row.get("data_point", ""),
            row.get("current_value", "") or "—",
            row.get("prior_reading", "") or "—",
            ARROWS.get(direction, direction or "—"),
            row.get("signal_implication", "") or "—",
            status,
        ]
        for j, (txt, w) in enumerate(zip(values, widths)):
            cell = cells[j]
            cell.text = txt
            set_cell_width(cell, w)
            bg = LIGHT_GREY if (i % 2 == 0 and not unavail) else None
            if unavail:
                bg = RGBColor(0xF2, 0xF2, 0xF2)
            if bg:
                set_cell_bg(cell, bg)
            color = MID_GREY if unavail else (DIR_COLOR.get(direction) if j == 3 else None)
            cell_font(cell, size=8, color=color,
                      align=(WD_ALIGN_PARAGRAPH.CENTER if j in (2, 3, 5)
                             else WD_ALIGN_PARAGRAPH.LEFT))

    add_borders(tbl)
    add_spacer(doc, 8)


# ---------------------------------------------------------------------------
# M2 — Sector Ranking
# ---------------------------------------------------------------------------

def section_m2(doc: Document, path: Path) -> None:
    add_section_heading(doc, "Sector Ranking")

    if not path.exists():
        add_note(doc, f"File not found: {path.name}")
        return

    text = path.read_text()
    m = re.search(r"Generated At:\s*(.+)", text)
    if m:
        add_note(doc, f"Generated: {m.group(1).strip()}")

    # Split on ## headings, render each sub-section
    parts = re.split(r"^## (.+)$", text, flags=re.MULTILINE)
    i = 1
    while i + 1 < len(parts):
        add_h2(doc, parts[i].strip())
        render_md_body(doc, parts[i + 1], font_size=9)
        i += 2


# ---------------------------------------------------------------------------
# M3A — Investment Universe
# ---------------------------------------------------------------------------

def section_m3a(doc: Document, path: Path) -> None:
    add_section_heading(doc, "Investment Universe")

    if not path.exists():
        add_note(doc, f"File not found: {path.name}")
        return

    data        = json.loads(path.read_text())
    cycle_date  = data.get("cycle_date", "")
    rot_score   = data.get("rotation_score", "?")
    cycle_phase = data.get("cycle_phase", "?")
    universe    = data.get("universe", [])

    add_note(doc, (
        f"Cycle date: {cycle_date}  ·  Rotation score: {rot_score}  ·  "
        f"Phase: {cycle_phase}  ·  Universe: {len(universe)} stocks"
    ))

    # Macro themes
    themes = data.get("macro_themes", [])
    if themes:
        add_h2(doc, "Active Macro Themes")
        for theme in themes:
            add_bullet(doc, theme, size=9)
        add_spacer(doc, 6)

    # Favoured sectors table
    favored = sorted(data.get("favored_sectors", []), key=lambda x: x.get("rank", 99))
    if favored:
        add_h2(doc, "Favoured Sectors")
        rows = [["Rank", "Sector", "ETF", "Target", "Thesis"]]
        for s in favored:
            thesis = s.get("thesis", "")
            rows.append([
                str(s.get("rank", "")),
                s.get("name", ""),
                s.get("etf", ""),
                str(s.get("target_count", "")),
                thesis[:130] + ("…" if len(thesis) > 130 else ""),
            ])
        make_table(doc, rows, font_size=8,
                   col_widths=[0.4, 1.1, 0.5, 0.6, 4.9])

    # Avoid sectors
    avoid = data.get("avoid_sectors", [])
    if avoid:
        add_h2(doc, "Sectors to Avoid")
        rows = [["Sector", "ETF", "Reason"]]
        for s in avoid:
            reason = s.get("reason", "")
            rows.append([
                s.get("name", ""),
                s.get("etf", ""),
                reason[:150] + ("…" if len(reason) > 150 else ""),
            ])
        make_table(doc, rows, font_size=8,
                   col_widths=[1.2, 0.5, 5.8])

    # Universe by sector
    if universe:
        add_h2(doc, "Candidate Universe by Sector")
        sector_map: dict[str, list[str]] = {}
        for s in universe:
            sector_map.setdefault(s.get("sector", "Other"), []).append(s.get("ticker", ""))
        rows = [["Sector", "Count", "Tickers"]]
        for sec, tickers in sorted(sector_map.items(), key=lambda x: -len(x[1])):
            rows.append([sec, str(len(tickers)), "  ".join(tickers)])
        make_table(doc, rows, font_size=8,
                   col_widths=[1.3, 0.6, 5.6])


# ---------------------------------------------------------------------------
# M3B — Stock Screening
# ---------------------------------------------------------------------------

def section_m3b(doc: Document, path: Path) -> None:
    add_section_heading(doc, "Stock Screening")

    if not path.exists():
        add_note(doc, f"File not found: {path.name}")
        return

    text = path.read_text()

    # Pre-output checks block
    pre = re.search(r"PRE-OUTPUT CHECKS\n-+\n([\s\S]+?)(?=\n---|\Z)", text, re.IGNORECASE)
    if pre:
        add_h2(doc, "Pre-Output Checks")
        for line in pre.group(1).strip().splitlines():
            s = line.strip()
            if not s:
                continue
            if re.match(r"^\d+\.", s):
                add_bullet(doc, re.sub(r"^\d+\.\s*", "", s), size=8)
            else:
                add_body(doc, s, size=8, color=DARK_GREY)
        add_spacer(doc, 6)

    # Locate the composite ranking table block
    rank_match = re.search(
        r"COMPOSITE RANKING[^\n]*\n-+\n([\s\S]+?)(?=\n---|WATCHLIST STOCKS|\Z)",
        text, re.IGNORECASE
    )
    if not rank_match:
        rank_match = re.search(
            r"FULL SCORING TABLE[^\n]*\n-+\n([\s\S]+?)(?=\n---|\Z)",
            text, re.IGNORECASE
        )

    if rank_match:
        raw  = rank_match.group(1)
        rows = parse_pipe_table(raw)

        if rows:
            add_h2(doc, "Composite Ranking")
            headers    = rows[0]
            status_idx = next(
                (i for i, h in enumerate(headers) if "status" in h.lower()), -1
            )
            ncols = max(len(r) for r in rows)
            rows  = [r + [""] * (ncols - len(r)) for r in rows]

            tbl = doc.add_table(rows=len(rows), cols=ncols)
            tbl.style     = "Table Grid"
            tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
            style_header_row(tbl.rows[0], font_size=8)

            for i, row in enumerate(rows):
                for j, txt in enumerate(row):
                    cell = tbl.rows[i].cells[j]
                    cell.text = txt
                    align = (WD_ALIGN_PARAGRAPH.CENTER
                             if j > 1 else WD_ALIGN_PARAGRAPH.LEFT)
                    cell_font(cell, size=8, align=align)
                if i == 0:
                    continue
                status = (row[status_idx].strip().upper()
                          if 0 <= status_idx < len(row) else "")
                if "ADVANCE" in status:
                    bg = ADV_COLOR
                elif "WATCH" in status:
                    bg = WTCH_COLOR
                elif "ELIM" in status:
                    bg = ELIM_COLOR
                elif i % 2 == 0:
                    bg = LIGHT_GREY
                else:
                    bg = None
                if bg:
                    for cell in tbl.rows[i].cells:
                        set_cell_bg(cell, bg)

            add_borders(tbl)
            add_spacer(doc, 8)
            add_color_legend(doc, [
                ("ADVANCE",    ADV_COLOR,  SIG_BUY_TXT),
                ("WATCHLIST",  WTCH_COLOR, SIG_HOLD_TXT),
                ("ELIMINATED", ELIM_COLOR, SIG_SKIP_TXT),
            ])


# ---------------------------------------------------------------------------
# M5 — Portfolio Construction  (hero section)
# ---------------------------------------------------------------------------

def section_m5(doc: Document, path: Path) -> None:
    add_section_heading(doc, "Portfolio Construction")

    if not path.exists():
        add_note(doc, (
            f"File not found: {path.name}  —  "
            "Run the full pipeline to generate this section."
        ))
        return

    text = path.read_text()

    # ---- 16-category scoring table ---------------------------------------
    tbl_match = re.search(r"((?:\|[^\n]+\|\n){2,})", text)
    if tbl_match:
        add_h2(doc, "16-Category Scoring Table")
        rows = parse_pipe_table(tbl_match.group(1))

        if rows:
            headers    = rows[0]
            signal_idx = next(
                (i for i, h in enumerate(headers) if h.strip().lower() == "signal"), -1
            )
            ncols = max(len(r) for r in rows)
            rows  = [r + [""] * (ncols - len(r)) for r in rows]

            tbl = doc.add_table(rows=len(rows), cols=ncols)
            tbl.style     = "Table Grid"
            tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
            style_header_row(tbl.rows[0], font_size=7)

            for i, row in enumerate(rows):
                for j, txt in enumerate(row):
                    cell = tbl.rows[i].cells[j]
                    cell.text = txt
                    cell_font(cell, size=7, align=WD_ALIGN_PARAGRAPH.CENTER)
                if i == 0:
                    continue

                signal = (row[signal_idx].strip().upper()
                          if 0 <= signal_idx < len(row) else "")
                if "BUY" in signal:
                    bg = SIG_BUY
                elif "HOLD" in signal:
                    bg = SIG_HOLD
                elif "WATCH" in signal:
                    bg = SIG_WATCH
                elif "SKIP" in signal:
                    bg = SIG_SKIP
                elif i % 2 == 0:
                    bg = LIGHT_GREY
                else:
                    bg = None
                if bg:
                    for cell in tbl.rows[i].cells:
                        set_cell_bg(cell, bg)

            add_borders(tbl)
            add_spacer(doc, 8)
            add_color_legend(doc, [
                ("BUY  (Score ≥ 110)",    SIG_BUY,   SIG_BUY_TXT),
                ("HOLD  (80 – 109)",       SIG_HOLD,  SIG_HOLD_TXT),
                ("WATCH  (60 – 79)",       SIG_WATCH, SIG_WATCH_TXT),
                ("SKIP  (< 60)",           SIG_SKIP,  SIG_SKIP_TXT),
            ])

    # ---- Narrative blocks (allocation + recommendations) -----------------
    # Remove table lines and render remaining headings + prose
    body = re.sub(r"(?:\|[^\n]+\|\n)+", "", text)
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.match(r"^## ", s):
            add_h2(doc, s[3:].strip())
        elif re.match(r"^# ", s):
            pass  # top-level title already handled by section heading
        else:
            clean = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
            clean = re.sub(r"\*(.+?)\*",     r"\1", clean)
            add_body(doc, clean, size=10)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build a formatted Word report from pipeline outputs."
    )
    p.add_argument(
        "--output", "-o", metavar="FILE",
        help="Output .docx path (default: investment-strategy-report-YYYY-MM-DD.docx)",
    )
    return p.parse_args()


def main() -> None:
    global _section_counter
    _section_counter = 0

    args  = parse_args()
    today = date.today().strftime("%Y-%m-%d")
    output_path = (
        Path(args.output) if args.output
        else BASE_DIR / f"investment-strategy-report-{today}.docx"
    )

    m1_meta: dict | None = None
    if M1_PATH.exists():
        try:
            m1_meta = json.loads(M1_PATH.read_text())
        except Exception:
            pass

    doc = Document()

    for sec in doc.sections:
        sec.top_margin    = Inches(0.80)
        sec.bottom_margin = Inches(0.75)
        sec.left_margin   = Inches(0.90)
        sec.right_margin  = Inches(0.90)

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10)

    print(f"Building report → {output_path.name}", flush=True)

    section_cover(doc, today, m1_meta)
    add_footer(doc, today)

    print("  [1/5] M1 Macro Environment ...", flush=True)
    section_m1(doc, M1_PATH)
    doc.add_page_break()

    print("  [2/5] M2 Sector Ranking ...", flush=True)
    section_m2(doc, M2_PATH)
    doc.add_page_break()

    print("  [3/5] M3A Investment Universe ...", flush=True)
    section_m3a(doc, M3U_PATH)
    doc.add_page_break()

    print("  [4/5] M3B Stock Screening ...", flush=True)
    section_m3b(doc, M3B_PATH)
    doc.add_page_break()

    print("  [5/5] M5 Portfolio Construction ...", flush=True)
    section_m5(doc, M5_PATH)

    doc.save(str(output_path))
    size_kb = output_path.stat().st_size / 1024

    # Also write a stable "latest" copy for pipeline stage verification
    latest_path = BASE_DIR / "investment-strategy-report-latest.docx"
    import shutil
    shutil.copy2(str(output_path), str(latest_path))

    print(f"\nDone  →  {output_path}  ({size_kb:.1f} KB)", flush=True)


if __name__ == "__main__":
    main()
