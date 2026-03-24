#!/usr/bin/env python3
"""Run the M3A universe generation prompt through the Anthropic Messages API."""

from __future__ import annotations

import argparse
import json
import sys
from json import JSONDecodeError
from pathlib import Path
from typing import Any

import anthropic


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.research_app.anthropic_runner import (  # noqa: E402
    extract_text_response,
    load_env_file,
    read_required_text,
    resolve_api_key,
    run_message_loop,
)

ENV_PATH = BASE_DIR / ".env"
DEFAULT_PROMPT_PATH = Path(__file__).parent / "prompt-universe-generation.md"
DEFAULT_SECTOR_INPUT_PATH = BASE_DIR / "M2 Sector ranking" / "output-sector-ranking-report.md"
DEFAULT_MACRO_INPUT_PATH = BASE_DIR / "M1 macro scan" / "output-research-macro-scan.json"
DEFAULT_OUTPUT_PATH = Path(__file__).parent / "output-universe-generation.json"
DEFAULT_DEBUG_TEXT_PATH = Path(__file__).parent / "output-universe-generation-last-response.txt"

ANTHROPIC_API_ENV_VAR = "ANTHROPIC_API_KEY"
ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_MODEL_LABEL = "Claude Sonnet 4.6"
WEB_SEARCH_TOOL_TYPE = "web_search_20260209"
MAX_OUTPUT_TOKENS = 16000
DEFAULT_TEMPERATURE = 0.0
DEFAULT_WEB_SEARCH_MAX_USES = 20
DEFAULT_MAX_PAUSE_TURNS = 4
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_BASE_DELAY = 2.0
DEFAULT_RETRY_MAX_DELAY = 60.0


class AnthropicRunnerError(RuntimeError):
    """Base error for universe generation runner failures."""


def build_user_message(
    sector_report_text: str,
    macro_scan_text: str,
) -> str:
    return (
        "Use the files below as the complete working context.\n\n"
        "FILE: M2 Sector ranking/sector-ranking-report.md\n"
        "```md\n"
        f"{sector_report_text.strip()}\n"
        "```\n\n"
        "FILE: M1 macro scan/research-macro-scan.json\n"
        "```json\n"
        f"{macro_scan_text.strip()}\n"
        "```\n\n"
        "Return only the final JSON code block for "
        "`M3A Universe generation/universe-generation.json`. "
        "Do not add commentary before or after the JSON code block."
    )


def build_tools(
    enable_web_search: bool,
    web_search_tool_type: str,
    web_search_max_uses: int,
) -> list[dict[str, Any]] | None:
    if not enable_web_search:
        return None
    return [
        {
            "type": web_search_tool_type,
            "name": "web_search",
            "max_uses": web_search_max_uses,
        }
    ]


def parse_json_payload(text: str) -> dict[str, Any]:
    if not text:
        raise AnthropicRunnerError("Anthropic returned an empty text response.")

    # 1. Try direct parse — response is pure JSON
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except JSONDecodeError:
        pass

    # 2. Find any ```json ... ``` or ``` ... ``` block anywhere in the text
    import re
    for block_match in re.finditer(r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.DOTALL):
        inner = block_match.group(1).strip()
        try:
            payload = json.loads(inner)
            if isinstance(payload, dict):
                return payload
        except JSONDecodeError:
            pass

    # 3. Find the largest valid JSON object starting from any { in the text
    decoder = json.JSONDecoder()
    best: dict[str, Any] | None = None
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(text[index:])
        except JSONDecodeError:
            continue
        if isinstance(candidate, dict) and len(candidate) > len(best or {}):
            best = candidate

    if best is not None:
        return best

    raise AnthropicRunnerError(
        "Anthropic response was not valid JSON. Raw text response could not be parsed."
    )


def write_debug_artifacts(response_text: str) -> None:
    DEFAULT_DEBUG_TEXT_PATH.write_text(response_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the M3A universe generation prompt with Anthropic Claude."
    )
    parser.add_argument(
        "--prompt-file",
        default=str(DEFAULT_PROMPT_PATH),
        help="Path to the universe-generation prompt markdown file.",
    )
    parser.add_argument(
        "--sector-input-file",
        default=str(DEFAULT_SECTOR_INPUT_PATH),
        help="Path to the M2 sector ranking report markdown file.",
    )
    parser.add_argument(
        "--macro-input-file",
        default=str(DEFAULT_MACRO_INPUT_PATH),
        help="Path to the M1 macro scan JSON file.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Where to write the final universe-generation JSON output.",
    )
    parser.add_argument(
        "--api-key",
        help="Override ANTHROPIC_API_KEY from the environment.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help="Sampling temperature.",
    )
    parser.add_argument(
        "--disable-web-search",
        action="store_true",
        help="Disable Anthropic web search tool usage for this run.",
    )
    parser.add_argument(
        "--web-search-max-uses",
        type=int,
        default=DEFAULT_WEB_SEARCH_MAX_USES,
        help="Maximum Anthropic web searches allowed during the run.",
    )
    parser.add_argument(
        "--max-pause-turns",
        type=int,
        default=DEFAULT_MAX_PAUSE_TURNS,
        help="How many pause_turn continuations to allow for server tools.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help="Maximum retry attempts on transient network/server errors.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the request and print metadata without calling Anthropic.",
    )
    return parser.parse_args()


def main() -> None:
    load_env_file(ENV_PATH)
    args = parse_args()

    prompt_path = Path(args.prompt_file)
    sector_input_path = Path(args.sector_input_file)
    macro_input_path = Path(args.macro_input_file)
    output_path = Path(args.output)

    enable_web_search = not args.disable_web_search

    system_prompt = read_required_text(prompt_path, "prompt file", AnthropicRunnerError)
    sector_report_text = read_required_text(sector_input_path, "sector ranking report file", AnthropicRunnerError)
    macro_scan_text = read_required_text(macro_input_path, "macro scan file", AnthropicRunnerError)
    user_message = build_user_message(
        sector_report_text=sector_report_text,
        macro_scan_text=macro_scan_text,
    )

    tools = build_tools(
        enable_web_search=enable_web_search,
        web_search_tool_type=WEB_SEARCH_TOOL_TYPE,
        web_search_max_uses=args.web_search_max_uses,
    )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "model": ANTHROPIC_MODEL,
                    "model_label": ANTHROPIC_MODEL_LABEL,
                    "prompt_file": str(prompt_path),
                    "sector_input_file": str(sector_input_path),
                    "macro_input_file": str(macro_input_path),
                    "output_file": str(output_path),
                    "web_search_enabled": enable_web_search,
                    "web_search_tool_type": WEB_SEARCH_TOOL_TYPE if enable_web_search else None,
                    "web_search_max_uses": args.web_search_max_uses if enable_web_search else 0,
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                    "temperature": args.temperature,
                },
                indent=2,
            )
        )
        return

    api_key = resolve_api_key(args.api_key, ANTHROPIC_API_ENV_VAR, AnthropicRunnerError)
    client = anthropic.Anthropic(api_key=api_key)

    print(f"[universe-generation] Starting ({ANTHROPIC_MODEL_LABEL})", flush=True)
    print(f"  web_search={'enabled (max ' + str(args.web_search_max_uses) + ' uses)' if enable_web_search else 'disabled'}", flush=True)
    print("  Streaming response:\n", flush=True)

    response = run_message_loop(
        client=client,
        model=ANTHROPIC_MODEL,
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=MAX_OUTPUT_TOKENS,
        temperature=args.temperature,
        tools=tools,
        max_pause_turns=args.max_pause_turns,
        max_retries=args.max_retries,
        base_delay=DEFAULT_RETRY_BASE_DELAY,
        max_delay=DEFAULT_RETRY_MAX_DELAY,
        error_cls=AnthropicRunnerError,
    )

    print("\n", flush=True)

    response_text = extract_text_response(response)
    write_debug_artifacts(response_text)

    if not response_text:
        raise AnthropicRunnerError(
            "Anthropic returned an empty text response. "
            f"The last response was saved to {DEFAULT_DEBUG_TEXT_PATH}."
        )
    if response.stop_reason == "max_tokens":
        raise AnthropicRunnerError(
            "Anthropic stopped at max_tokens before finishing valid JSON. "
            f"The last response was saved to {DEFAULT_DEBUG_TEXT_PATH}."
        )

    try:
        payload = parse_json_payload(response_text)
    except AnthropicRunnerError as parse_err:
        if output_path.exists():
            print(
                f"\n  [WARNING] JSON parse failed: {parse_err}\n"
                f"  Falling back to existing {output_path.name} — pipeline will continue.",
                flush=True,
            )
            print(
                json.dumps(
                    {
                        "output_file": str(output_path),
                        "model": ANTHROPIC_MODEL,
                        "model_label": ANTHROPIC_MODEL_LABEL,
                        "stop_reason": response.stop_reason,
                        "usage": response.usage.model_dump() if response.usage else {},
                        "web_search_enabled": enable_web_search,
                        "max_output_tokens": MAX_OUTPUT_TOKENS,
                        "fallback": True,
                    },
                    indent=2,
                )
            )
            return
        raise

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "output_file": str(output_path),
                "model": ANTHROPIC_MODEL,
                "model_label": ANTHROPIC_MODEL_LABEL,
                "stop_reason": response.stop_reason,
                "usage": response.usage.model_dump() if response.usage else {},
                "web_search_enabled": enable_web_search,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
