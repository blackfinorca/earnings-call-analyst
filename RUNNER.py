#!/usr/bin/env python3
"""Pipeline runner — executes all research phases in sequence."""

from __future__ import annotations

import argparse
import itertools
import json
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# ANSI helpers (gracefully disabled if not a TTY)
# ---------------------------------------------------------------------------

_TTY = sys.stdout.isatty()

GREEN  = "\033[32m"  if _TTY else ""
YELLOW = "\033[33m"  if _TTY else ""
RED    = "\033[31m"  if _TTY else ""
CYAN   = "\033[36m"  if _TTY else ""
BOLD   = "\033[1m"   if _TTY else ""
DIM    = "\033[2m"   if _TTY else ""
RESET  = "\033[0m"   if _TTY else ""

WIDTH = 64


def bar(done: int, total: int, width: int = 32) -> str:
    filled = round(width * done / total) if total else 0
    return f"[{GREEN}{'█' * filled}{RESET}{'░' * (width - filled)}] {done}/{total}"


def fmt_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


def fmt_tokens(n: int | None) -> str:
    if n is None:
        return "—"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------

@dataclass
class Stage:
    id: str
    label: str
    description: str
    script: str           # relative to BASE_DIR
    output: str           # relative to BASE_DIR — verified after run
    supports_dry_run: bool = True
    extra_args: list[str] = field(default_factory=list)


STAGES: list[Stage] = [
    Stage(
        id="m1",
        label="M1  Macro Scan",
        description=(
            "Fetches live macro indicators (GDP, inflation, rates, PMI, oil)\n"
            "    via FMP & Yahoo Finance APIs and writes a structured JSON snapshot."
        ),
        script="M1 macro scan/script-research-functions.py",
        output="M1 macro scan/output-research-macro-scan.json",
        supports_dry_run=False,
    ),
    Stage(
        id="m2",
        label="M2  Sector Ranking",
        description=(
            "Runs Claude Sonnet with live web search to rank sectors by macro\n"
            "    cycle alignment and produces a weighted sector ranking report."
        ),
        script="M2 Sector ranking/script-sector-ranking.py",
        output="M2 Sector ranking/output-sector-ranking-report.md",
    ),
    Stage(
        id="m3a-universe",
        label="M3A Universe Generation (AI)",
        description=(
            "Claude Sonnet searches the web per-sector and selects 40-50\n"
            "    candidate stocks aligned with the current macro theme."
        ),
        script="M3A Universe generation/script-universe-generation.py",
        output="M3A Universe generation/output-universe-generation.json",
    ),
    Stage(
        id="m3a-api",
        label="M3A Universe API Data Fetch",
        description=(
            "Fetches 12-month price history and fundamentals for every\n"
            "    ticker via yfinance. Always fetches fresh data on each run."
        ),
        script="M3A Universe generation/script-universe-generation-api.py",
        output="M3A Universe generation/output-universe-generation-api.json",
        supports_dry_run=False,
    ),
    Stage(
        id="m3b",
        label="M3B Stock Screening",
        description=(
            "Claude Sonnet scores every stock across 5 lenses (rotation,\n"
            "    macro, factor, quality, diversification) and ranks them."
        ),
        script="M3B stock screening/script-stock-screening.py",
        output="M3B stock screening/output-stock-screener.txt",
    ),
    Stage(
        id="m5",
        label="M5  Portfolio Construction",
        description=(
            "Claude Sonnet builds a concentrated equity portfolio from the\n"
            "    scored universe, applying a 16-category tiered scoring model."
        ),
        script="M5 Portfolio construction/script-portfolio-construction.py",
        output="M5 Portfolio construction/output-portfolio-construction.md",
    ),
    Stage(
        id="doc",
        label="DOC Report Builder",
        description=(
            "Assembles a formatted Word (.docx) report from all phase outputs\n"
            "    (M1–M5) with professional layout and signal-coloured tables."
        ),
        script="document-builder.py",
        output="investment-strategy-report-latest.docx",
        supports_dry_run=False,
    ),
]

STAGE_IDS = [s.id for s in STAGES]


# ---------------------------------------------------------------------------
# Stage result
# ---------------------------------------------------------------------------

@dataclass
class StageResult:
    stage: Stage
    elapsed: float
    success: bool
    model_label: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


# ---------------------------------------------------------------------------
# Live elapsed-time spinner (shown on stderr while subprocess runs)
# ---------------------------------------------------------------------------

class LiveTimer:
    """Prints a spinning elapsed-time indicator on stderr while active."""

    _FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, label: str) -> None:
        self._label = label
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._start = 0.0

    def start(self) -> None:
        self._start = time.monotonic()
        if _TTY:
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if _TTY and self._thread.is_alive():
            self._thread.join()
            print(f"\r{' ' * (WIDTH + 10)}\r", end="", file=sys.stderr, flush=True)

    def elapsed(self) -> float:
        return time.monotonic() - self._start

    def _run(self) -> None:
        for frame in itertools.cycle(self._FRAMES):
            if self._stop.is_set():
                break
            elapsed = time.monotonic() - self._start
            print(
                f"\r  {CYAN}{frame}{RESET}  {self._label}  {DIM}{fmt_time(elapsed)} elapsed{RESET}",
                end="",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(0.1)


# ---------------------------------------------------------------------------
# Usage parser — extracts model + token counts from captured script output
# ---------------------------------------------------------------------------

def parse_usage(output: str) -> tuple[str | None, int | None, int | None]:
    """
    Scan captured stdout for the final JSON summary block that scripts emit.
    Returns (model_label, input_tokens, output_tokens). Any field may be None.
    """
    decoder = json.JSONDecoder()
    model_label: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    for match in re.finditer(r"\{", output):
        try:
            obj, _ = decoder.raw_decode(output, match.start())
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        # Only consider objects that carry LLM usage info
        if "usage" not in obj and "model_label" not in obj:
            continue
        if "model_label" in obj:
            model_label = obj["model_label"]
        usage = obj.get("usage") or {}
        if "input_tokens" in usage:
            input_tokens = usage["input_tokens"]
        if "output_tokens" in usage:
            output_tokens = usage["output_tokens"]

    return model_label, input_tokens, output_tokens


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def print_divider(char: str = "─") -> None:
    print(char * WIDTH)


def print_pipeline_overview(
    stages_to_run: list[Stage],
    completed: set[str],
    current_id: str | None,
    failed_id: str | None,
) -> None:
    total = len(stages_to_run)
    done = len(completed)

    print()
    print_divider("═")
    print(f"{BOLD}  INVESTMENT STRATEGY RESEARCH PIPELINE{RESET}")
    print_divider("═")
    print(f"\n  Pipeline progress  {bar(done, total)}\n")

    for stage in stages_to_run:
        if stage.id in completed:
            icon   = f"{GREEN}✓{RESET}"
            status = f"{GREEN}done{RESET}"
        elif stage.id == failed_id:
            icon   = f"{RED}✗{RESET}"
            status = f"{RED}failed{RESET}"
        elif stage.id == current_id:
            icon   = f"{YELLOW}▶{RESET}"
            status = f"{YELLOW}running{RESET}"
        else:
            icon   = f"{DIM}○{RESET}"
            status = f"{DIM}pending{RESET}"

        print(f"  {icon}  {stage.label:<38} {status}")

    print()
    print_divider("═")
    print()


def print_stage_header(stage: Stage, index: int, total: int, dry_run: bool) -> None:
    print_divider()
    tag = f"[{index}/{total}]"
    mode = f"  {YELLOW}DRY RUN{RESET}" if (dry_run and stage.supports_dry_run) else ""
    print(f"  {BOLD}{CYAN}{tag}{RESET}  {BOLD}{stage.label}{RESET}{mode}")
    print_divider()
    print(f"\n  {stage.description}\n")
    print(f"  {DIM}script :{RESET} {stage.script}")
    print(f"  {DIM}output :{RESET} {stage.output}")
    print()


def print_stage_result(result: StageResult, dry_run: bool) -> None:
    stage = result.stage
    if not result.success:
        print(f"\n  {RED}✗  FAILED{RESET}  —  {stage.label}  ({fmt_time(result.elapsed)})")
        print_divider()
        return

    output_path = BASE_DIR / stage.output
    if not dry_run and output_path.exists():
        size_kb = output_path.stat().st_size / 1024
        file_info = f"  {DIM}→{RESET} {output_path.name}  ({size_kb:.1f} KB)"
    else:
        file_info = ""

    print(f"\n  {GREEN}✓  DONE{RESET}  —  {stage.label}  ({fmt_time(result.elapsed)})")
    if file_info:
        print(file_info)
    print_divider()


def print_summary(results: list[StageResult]) -> None:
    total_time = sum(r.elapsed for r in results)
    all_ok = all(r.success for r in results)

    total_in  = sum(r.input_tokens  for r in results if r.input_tokens  is not None)
    total_out = sum(r.output_tokens for r in results if r.output_tokens is not None)
    has_tokens = any(r.input_tokens is not None for r in results)

    print()
    print_divider("═")
    status_word = "COMPLETE" if all_ok else "FAILED"
    print(f"{BOLD}  PIPELINE {status_word}  —  {fmt_time(total_time)} total{RESET}")
    print_divider("═")
    print()

    # Column widths
    C_STAGE  = 36
    C_TIME   =  8
    C_MODEL  = 22
    C_IN     =  9
    C_OUT    =  9

    header = (
        f"  {'Stage':<{C_STAGE}} {'Time':>{C_TIME}}  "
        f"{'Model':<{C_MODEL}} {'In tok':>{C_IN}} {'Out tok':>{C_OUT}}"
    )
    print(f"{DIM}{header}{RESET}")
    print(f"  {'─' * (C_STAGE + C_TIME + C_MODEL + C_IN + C_OUT + 6)}")

    for r in results:
        icon  = f"{GREEN}✓{RESET}" if r.success else f"{RED}✗{RESET}"
        model = r.model_label or f"{DIM}—{RESET}"
        in_t  = fmt_tokens(r.input_tokens)
        out_t = fmt_tokens(r.output_tokens)
        print(
            f"  {icon} {r.stage.label:<{C_STAGE}} {fmt_time(r.elapsed):>{C_TIME}}  "
            f"{model:<{C_MODEL}} {in_t:>{C_IN}} {out_t:>{C_OUT}}"
        )

    if has_tokens:
        print(f"  {'─' * (C_STAGE + C_TIME + C_MODEL + C_IN + C_OUT + 6)}")
        print(
            f"  {'  Total':<{C_STAGE + 2}} {fmt_time(total_time):>{C_TIME}}  "
            f"{'':>{C_MODEL}} {fmt_tokens(total_in):>{C_IN}} {fmt_tokens(total_out):>{C_OUT}}"
        )

    print()
    print_divider("═")
    print()


# ---------------------------------------------------------------------------
# Stage runner
# ---------------------------------------------------------------------------

def run_stage(stage: Stage, dry_run: bool) -> StageResult:
    """Run one stage, streaming output to stdout while capturing it for parsing."""
    script_path = BASE_DIR / stage.script
    output_path = BASE_DIR / stage.output

    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    cmd = [sys.executable, "-u", str(script_path), *stage.extra_args]
    if dry_run and stage.supports_dry_run:
        cmd.append("--dry-run")

    timer = LiveTimer(stage.label)
    timer.start()

    captured_lines: list[str] = []
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=None,       # inherit — subprocess stderr goes straight to terminal
            text=True,
            bufsize=1,         # line-buffered
            cwd=str(BASE_DIR),
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="", flush=True)
            captured_lines.append(line)
        proc.wait()
    finally:
        timer.stop()

    elapsed = timer.elapsed()
    output_text = "".join(captured_lines)

    if proc.returncode != 0:
        raise RuntimeError(
            f"Stage '{stage.id}' exited with code {proc.returncode}."
        )

    if not dry_run and not output_path.exists():
        raise RuntimeError(
            f"Stage '{stage.id}' succeeded but output file is missing: {output_path}"
        )

    model_label, input_tokens, output_tokens = parse_usage(output_text)
    return StageResult(
        stage=stage,
        elapsed=elapsed,
        success=True,
        model_label=model_label,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the investment strategy research pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Stages (in order):\n"
            + "\n".join(f"  {s.id:<16} {s.label}" for s in STAGES)
        ),
    )
    parser.add_argument(
        "--from",
        dest="from_stage",
        metavar="STAGE",
        choices=STAGE_IDS,
        help="Start from this stage, skipping all earlier stages.",
    )
    parser.add_argument(
        "--only",
        metavar="STAGE",
        choices=STAGE_IDS,
        help="Run only this single stage.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pass --dry-run to every script (no API calls made).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    if args.only:
        stages_to_run = [s for s in STAGES if s.id == args.only]
    elif args.from_stage:
        start_idx = STAGE_IDS.index(args.from_stage)
        stages_to_run = STAGES[start_idx:]
    else:
        stages_to_run = STAGES

    completed: set[str] = set()
    results: list[StageResult] = []

    print_pipeline_overview(stages_to_run, completed, stages_to_run[0].id, None)

    for i, stage in enumerate(stages_to_run, 1):
        print_stage_header(stage, i, len(stages_to_run), args.dry_run)

        try:
            result = run_stage(stage, dry_run=args.dry_run)
        except (RuntimeError, FileNotFoundError) as exc:
            failed = StageResult(stage=stage, elapsed=0.0, success=False)
            print_stage_result(failed, args.dry_run)
            results.append(failed)
            print(f"  {RED}Error:{RESET} {exc}", file=sys.stderr)
            print_summary(results)
            sys.exit(1)

        completed.add(stage.id)
        results.append(result)
        print_stage_result(result, args.dry_run)

        next_id = stages_to_run[i].id if i < len(stages_to_run) else None
        print_pipeline_overview(stages_to_run, completed, next_id, None)

    print_summary(results)


if __name__ == "__main__":
    main()
