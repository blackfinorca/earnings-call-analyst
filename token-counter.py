#!/usr/bin/env python3
"""Count input and output tokens for each project phase."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tiktoken  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    tiktoken = None


BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class PhaseSpec:
    phase_id: str
    name: str
    inputs: tuple[Path, ...]
    outputs: tuple[Path, ...]
    notes: str = ""


PHASE_SPECS: dict[str, PhaseSpec] = {
    "M1": PhaseSpec(
        phase_id="M1",
        name="Macro Scan",
        inputs=(BASE_DIR / "M1 macro scan" / "research-functions.py",),
        outputs=(BASE_DIR / "M1 macro scan" / "research-macro-scan.json",),
        notes="M1 is code-driven, so the input count is based on the phase entry script.",
    ),
    "M2": PhaseSpec(
        phase_id="M2",
        name="Sector Ranking",
        inputs=(
            BASE_DIR / "M2 Sector ranking" / "sector-ranking.md",
            BASE_DIR / "writing-phylosophy.jsx",
            BASE_DIR / "M1 macro scan" / "research-macro-scan.json",
        ),
        outputs=(BASE_DIR / "M2 Sector ranking" / "sector-ranking-report.md",),
        notes="M2 input count is based on the files sent to the model.",
    ),
    "M3": PhaseSpec(
        phase_id="M3",
        name="Universe Generation",
        inputs=(
            BASE_DIR / "M3A Universe generation" / "universe-generation.md",
            BASE_DIR / "M2 Sector ranking" / "sector-ranking-report.md",
            BASE_DIR / "M1 macro scan" / "research-macro-scan.json",
        ),
        outputs=(BASE_DIR / "M3A Universe generation" / "universe-generation.json",),
        notes="M3A input count is based on the upstream files sent to the model.",
    ),
    "M4": PhaseSpec(
        phase_id="M4",
        name="TBD",
        inputs=(),
        outputs=(),
        notes="Placeholder for future phase wiring.",
    ),
    "M5": PhaseSpec(
        phase_id="M5",
        name="TBD",
        inputs=(),
        outputs=(),
        notes="Placeholder for future phase wiring.",
    ),
    "M6": PhaseSpec(
        phase_id="M6",
        name="TBD",
        inputs=(),
        outputs=(),
        notes="Placeholder for future phase wiring.",
    ),
}


def count_tokens(text: str) -> tuple[int, str]:
    if tiktoken is not None:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text)), "tiktoken:cl100k_base"
    return math.ceil(len(text) / 4), "approx:chars_per_token"


def describe_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "bytes": 0,
            "tokens": 0,
        }

    text = path.read_text(encoding="utf-8", errors="replace")
    tokens, tokenizer = count_tokens(text)
    return {
        "path": str(path),
        "exists": True,
        "bytes": len(text.encode("utf-8")),
        "tokens": tokens,
        "tokenizer": tokenizer,
    }


def summarize_paths(paths: tuple[Path, ...]) -> dict[str, Any]:
    files = [describe_file(path) for path in paths]
    return {
        "count": len(files),
        "tokens": sum(file_info["tokens"] for file_info in files),
        "bytes": sum(file_info["bytes"] for file_info in files),
        "missing_files": [file_info["path"] for file_info in files if not file_info["exists"]],
        "files": files,
    }


def build_phase_report(spec: PhaseSpec) -> dict[str, Any]:
    input_summary = summarize_paths(spec.inputs)
    output_summary = summarize_paths(spec.outputs)
    return {
        "phase_id": spec.phase_id,
        "name": spec.name,
        "notes": spec.notes,
        "input": input_summary,
        "output": output_summary,
        "net_tokens": output_summary["tokens"] - input_summary["tokens"],
    }


def build_report(selected_phases: list[str]) -> dict[str, Any]:
    phase_reports = [build_phase_report(PHASE_SPECS[phase_id]) for phase_id in selected_phases]
    tokenizer = "tiktoken:cl100k_base" if tiktoken is not None else "approx:chars_per_token"
    return {
        "tool": "token-counter",
        "tokenizer": tokenizer,
        "phases": phase_reports,
        "totals": {
            "input_tokens": sum(report["input"]["tokens"] for report in phase_reports),
            "output_tokens": sum(report["output"]["tokens"] for report in phase_reports),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Count input and output tokens by phase.")
    parser.add_argument(
        "--phase",
        action="append",
        choices=sorted(PHASE_SPECS.keys()),
        help="Limit the report to one or more phases. Defaults to all phases.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a text report.",
    )
    return parser.parse_args()


def print_text_report(report: dict[str, Any]) -> None:
    print(f"Tokenizer: {report['tokenizer']}")
    print()
    for phase in report["phases"]:
        print(f"{phase['phase_id']} {phase['name']}")
        if phase["notes"]:
            print(f"  Notes: {phase['notes']}")
        print(f"  Input tokens: {phase['input']['tokens']}")
        for file_info in phase["input"]["files"]:
            status = "missing" if not file_info["exists"] else f"{file_info['tokens']} tokens"
            print(f"    - {file_info['path']}: {status}")
        print(f"  Output tokens: {phase['output']['tokens']}")
        for file_info in phase["output"]["files"]:
            status = "missing" if not file_info["exists"] else f"{file_info['tokens']} tokens"
            print(f"    - {file_info['path']}: {status}")
        print(f"  Net tokens: {phase['net_tokens']}")
        print()
    print(f"Total input tokens: {report['totals']['input_tokens']}")
    print(f"Total output tokens: {report['totals']['output_tokens']}")


def main() -> None:
    args = parse_args()
    selected_phases = args.phase or list(PHASE_SPECS.keys())
    report = build_report(selected_phases)
    if args.json:
        print(json.dumps(report, indent=2))
        return
    print_text_report(report)


if __name__ == "__main__":
    main()
