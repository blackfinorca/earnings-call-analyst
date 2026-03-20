#!/usr/bin/env python3
"""Run the M5 portfolio construction prompt through the Anthropic Messages API."""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path
from typing import Any

import anthropic


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"
DEFAULT_PROMPT_PATH = Path(__file__).parent / "prompt-portfolio-construction.md"
DEFAULT_SCREENER_INPUT_PATH = BASE_DIR / "M3B stock screening" / "output-stock-screener.txt"
DEFAULT_API_INPUT_PATH = BASE_DIR / "M3A Universe generation" / "output-universe-generation-api.json"
DEFAULT_MACRO_INPUT_PATH = BASE_DIR / "M1 macro scan" / "output-research-macro-scan.json"
DEFAULT_OUTPUT_PATH = Path(__file__).parent / "output-portfolio-construction.md"

ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_MODEL_LABEL = "Claude Sonnet 4.6"

MAX_OUTPUT_TOKENS = 32000
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_PAUSE_TURNS = 4
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_BASE_DELAY = 2.0
DEFAULT_RETRY_MAX_DELAY = 60.0


class RunnerError(RuntimeError):
    """Base error for portfolio construction runner failures."""


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

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        return api_key

    raise RunnerError(
        "Missing ANTHROPIC_API_KEY. Set it in .env or export it in the shell."
    )


def read_required_text(path: Path, label: str) -> str:
    if not path.exists():
        raise RunnerError(f"Missing {label}: {path}")
    return path.read_text(encoding="utf-8")


def build_user_message(
    screener_text: str,
    api_input_text: str,
    macro_text: str,
) -> str:
    return (
        "Use the files below as the complete working context.\n\n"
        "FILE: M3B stock screening/stock-screener.txt\n"
        "```\n"
        f"{screener_text.strip()}\n"
        "```\n\n"
        "FILE: M3A Universe generation/universe-generation-api.json\n"
        "```json\n"
        f"{api_input_text.strip()}\n"
        "```\n\n"
        "FILE: M1 macro scan/research-macro-scan.json\n"
        "```json\n"
        f"{macro_text.strip()}\n"
        "```\n\n"
        "Construct the portfolio and produce the full 8-section output as "
        "specified in the prompt. Write plain text only — no markdown formatting. "
        "Do NOT output reasoning steps or intermediate calculations — "
        "output ONLY the final report starting with ## PORTFOLIO SUMMARY."
    )


def stream_with_retry(
    *,
    client: anthropic.Anthropic,
    model: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    temperature: float,
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
                raise
            last_exc = exc
            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
        except anthropic.APIConnectionError as exc:
            last_exc = exc
            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)

        print(f"\n[Retry {attempt + 1}/{max_retries}] Waiting {delay:.1f}s before retrying...", flush=True)
        time.sleep(delay)

    raise RunnerError(
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

    raise RunnerError(
        "Anthropic response hit repeated pause_turn limits before producing a final answer."
    )


def extract_text_response(response: anthropic.types.Message) -> str:
    parts: list[str] = []
    for block in response.content:
        if block.type == "text" and block.text:
            parts.append(block.text)
    return "\n".join(parts).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the M5 portfolio construction prompt with Anthropic Claude."
    )
    parser.add_argument(
        "--prompt-file",
        default=str(DEFAULT_PROMPT_PATH),
        help="Path to the portfolio-construction prompt markdown file.",
    )
    parser.add_argument(
        "--screener-input-file",
        default=str(DEFAULT_SCREENER_INPUT_PATH),
        help="Path to the M3B stock-screener.txt file.",
    )
    parser.add_argument(
        "--api-input-file",
        default=str(DEFAULT_API_INPUT_PATH),
        help="Path to the universe-generation-api.json file.",
    )
    parser.add_argument(
        "--macro-input-file",
        default=str(DEFAULT_MACRO_INPUT_PATH),
        help="Path to the M1 macro scan JSON file.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Where to write the portfolio construction report text output.",
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
        "--max-pause-turns",
        type=int,
        default=DEFAULT_MAX_PAUSE_TURNS,
        help="How many pause_turn continuations to allow.",
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
    screener_input_path = Path(args.screener_input_file)
    api_input_path = Path(args.api_input_file)
    macro_input_path = Path(args.macro_input_file)
    output_path = Path(args.output)

    system_prompt = read_required_text(prompt_path, "prompt file")
    screener_text = read_required_text(screener_input_path, "stock-screener.txt")
    api_input_text = read_required_text(api_input_path, "universe-generation-api.json")
    macro_text = read_required_text(macro_input_path, "research-macro-scan.json")
    user_message = build_user_message(
        screener_text=screener_text,
        api_input_text=api_input_text,
        macro_text=macro_text,
    )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "model": ANTHROPIC_MODEL,
                    "model_label": ANTHROPIC_MODEL_LABEL,
                    "prompt_file": str(prompt_path),
                    "screener_input_file": str(screener_input_path),
                    "api_input_file": str(api_input_path),
                    "macro_input_file": str(macro_input_path),
                    "output_file": str(output_path),
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                    "temperature": args.temperature,
                },
                indent=2,
            )
        )
        return

    api_key = resolve_api_key(args.api_key)
    client = anthropic.Anthropic(api_key=api_key)

    print(f"[portfolio-construction] Starting ({ANTHROPIC_MODEL_LABEL})", flush=True)
    print("  Streaming response:\n", flush=True)

    response = run_message_loop(
        client=client,
        model=ANTHROPIC_MODEL,
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=MAX_OUTPUT_TOKENS,
        temperature=args.temperature,
        max_pause_turns=args.max_pause_turns,
        max_retries=args.max_retries,
        base_delay=DEFAULT_RETRY_BASE_DELAY,
        max_delay=DEFAULT_RETRY_MAX_DELAY,
    )

    print("\n", flush=True)

    response_text = extract_text_response(response)

    if not response_text:
        raise RunnerError("Anthropic returned an empty text response.")
    if response.stop_reason == "max_tokens":
        raise RunnerError(
            "Anthropic stopped at max_tokens before finishing the report. "
            f"Partial output saved to {output_path}."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(response_text + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "output_file": str(output_path),
                "model": ANTHROPIC_MODEL,
                "model_label": ANTHROPIC_MODEL_LABEL,
                "stop_reason": response.stop_reason,
                "usage": response.usage.model_dump() if response.usage else {},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
