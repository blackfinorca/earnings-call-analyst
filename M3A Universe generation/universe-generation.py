#!/usr/bin/env python3
"""Run the M3A universe generation prompt through the Anthropic Messages API."""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from json import JSONDecodeError
from pathlib import Path
from typing import Any

import anthropic


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"
DEFAULT_PROMPT_PATH = Path(__file__).with_suffix(".md")
DEFAULT_SECTOR_INPUT_PATH = BASE_DIR / "M2 Sector ranking" / "sector-ranking-report.md"
DEFAULT_MACRO_INPUT_PATH = BASE_DIR / "M1 macro scan" / "research-macro-scan.json"
DEFAULT_OUTPUT_PATH = Path(__file__).with_suffix(".json")
DEFAULT_DEBUG_RESPONSE_PATH = Path(__file__).with_name("universe-generation-last-response.json")
DEFAULT_DEBUG_TEXT_PATH = Path(__file__).with_name("universe-generation-last-response.txt")

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


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


def resolve_api_key(explicit_api_key: str | None) -> str:
    if explicit_api_key:
        return explicit_api_key

    api_key = os.getenv(ANTHROPIC_API_ENV_VAR)
    if api_key:
        return api_key

    raise AnthropicRunnerError(
        f"Missing {ANTHROPIC_API_ENV_VAR}. Set it in .env or export it in the shell."
    )


def read_required_text(path: Path, label: str) -> str:
    if not path.exists():
        raise AnthropicRunnerError(f"Missing {label}: {path}")
    return path.read_text(encoding="utf-8")


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


def stream_with_retry(
    *,
    client: anthropic.Anthropic,
    model: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    temperature: float,
    tools: list[dict[str, Any]] | None,
    max_retries: int,
    base_delay: float,
    max_delay: float,
) -> anthropic.types.Message:
    """Stream a message request with exponential backoff retry on transient errors."""
    kwargs: dict[str, Any] = {
        "model": model,
        "system": system_prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            with client.messages.stream(**kwargs) as stream:
                for text_chunk in stream.text_stream:
                    print(text_chunk, end="", flush=True)
                return stream.get_final_message()
        except anthropic.RateLimitError as exc:
            last_exc = exc
            retry_after = int(
                getattr(getattr(exc, "response", None), "headers", {}).get(
                    "retry-after", base_delay * (2 ** attempt)
                )
            )
            delay = min(retry_after + random.uniform(0, 1), max_delay)
        except anthropic.APIStatusError as exc:
            if exc.status_code < 500:
                raise  # 4xx client errors are not retryable
            last_exc = exc
            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
        except anthropic.APIConnectionError as exc:
            last_exc = exc
            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)

        print(f"\n[Retry {attempt + 1}/{max_retries}] Waiting {delay:.1f}s before retrying...", flush=True)
        time.sleep(delay)

    raise AnthropicRunnerError(
        f"Anthropic request failed after {max_retries} retries."
    ) from last_exc


def run_message_loop(
    *,
    client: anthropic.Anthropic,
    model: str,
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    temperature: float,
    tools: list[dict[str, Any]] | None,
    max_pause_turns: int,
    max_retries: int,
    base_delay: float,
    max_delay: float,
) -> anthropic.types.Message:
    """Stream the agentic loop, resuming on pause_turn up to max_pause_turns times."""
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]

    for turn in range(max_pause_turns + 1):
        if turn > 0:
            print(f"\n[Turn {turn + 1}] Resuming after pause_turn...", flush=True)

        response = stream_with_retry(
            client=client,
            model=model,
            system_prompt=system_prompt,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
        )

        if response.stop_reason != "pause_turn":
            return response

        messages = messages + [
            {
                "role": "assistant",
                "content": response.content,
            }
        ]

    raise AnthropicRunnerError(
        "Anthropic response hit repeated pause_turn limits before producing a final answer."
    )


def extract_text_response(response: anthropic.types.Message) -> str:
    parts: list[str] = []
    for block in response.content:
        if block.type == "text" and block.text:
            parts.append(block.text)
    return "\n".join(parts).strip()


def parse_json_payload(text: str) -> dict[str, Any]:
    if not text:
        raise AnthropicRunnerError("Anthropic returned an empty text response.")

    try:
        payload = json.loads(text)
    except JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        return payload

    fenced = text.strip()
    if fenced.startswith("```"):
        lines = fenced.splitlines()
        if len(lines) >= 3:
            inner = "\n".join(lines[1:-1]).strip()
            try:
                payload = json.loads(inner)
            except JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                return payload

    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character not in "{[":
            continue
        try:
            candidate, end_index = decoder.raw_decode(text[index:])
        except JSONDecodeError:
            continue
        if text[index + end_index :].strip():
            continue
        if isinstance(candidate, dict):
            return candidate

    raise AnthropicRunnerError(
        "Anthropic response was not valid JSON. Raw text response could not be parsed."
    )


def write_debug_artifacts(response: anthropic.types.Message, response_text: str) -> None:
    response_dict = response.model_dump()
    DEFAULT_DEBUG_RESPONSE_PATH.write_text(
        json.dumps(response_dict, indent=2) + "\n",
        encoding="utf-8",
    )
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
        "--raw-response-output",
        help="Optional path to save the raw Anthropic API response JSON.",
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
    raw_response_output = Path(args.raw_response_output) if args.raw_response_output else None

    enable_web_search = not args.disable_web_search

    system_prompt = read_required_text(prompt_path, "prompt file")
    sector_report_text = read_required_text(sector_input_path, "sector ranking report file")
    macro_scan_text = read_required_text(macro_input_path, "macro scan file")
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

    api_key = resolve_api_key(args.api_key)
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
    )

    print("\n", flush=True)

    response_text = extract_text_response(response)
    write_debug_artifacts(response, response_text)

    if not response_text:
        raise AnthropicRunnerError(
            "Anthropic returned an empty text response. "
            f"The last response was saved to {DEFAULT_DEBUG_RESPONSE_PATH} and "
            f"{DEFAULT_DEBUG_TEXT_PATH}."
        )
    if response.stop_reason == "max_tokens":
        raise AnthropicRunnerError(
            "Anthropic stopped at max_tokens before finishing valid JSON. "
            f"The last response was saved to {DEFAULT_DEBUG_RESPONSE_PATH} and "
            f"{DEFAULT_DEBUG_TEXT_PATH}."
        )

    payload = parse_json_payload(response_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if raw_response_output:
        raw_response_output.parent.mkdir(parents=True, exist_ok=True)
        raw_response_output.write_text(
            json.dumps(response.model_dump(), indent=2) + "\n",
            encoding="utf-8",
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
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
