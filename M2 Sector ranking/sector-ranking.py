#!/usr/bin/env python3
"""Run the M2 sector ranking prompt through the Anthropic Messages API."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"
DEFAULT_PROMPT_PATH = Path(__file__).with_suffix(".md")
DEFAULT_INPUT_PATH = BASE_DIR / "M1 macro scan" / "research-macro-scan.json"
DEFAULT_WRITING_PATH = BASE_DIR / "writing-phylosophy.jsx"
DEFAULT_OUTPUT_PATH = Path(__file__).with_suffix(".json")

ANTHROPIC_API_ENV_VAR = "ANTHROPIC_API_KEY"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL_ALIAS = "opus-4.6"
DEFAULT_MAX_TOKENS = 8192
DEFAULT_TEMPERATURE = 0.2
DEFAULT_WEB_SEARCH_MAX_USES = 4
DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_MAX_PAUSE_TURNS = 3


class AnthropicRunnerError(RuntimeError):
    """Base error for sector ranking runner failures."""


@dataclass(frozen=True)
class ModelSpec:
    alias: str
    model_id: str
    description: str
    web_search_tool_type: str = "web_search_20250305"


MODEL_SPECS = {
    "opus-4.6": ModelSpec(
        alias="opus-4.6",
        model_id="claude-opus-4-6",
        description="Default flagship Opus model.",
        web_search_tool_type="web_search_20260209",
    ),
    "opus-4.5": ModelSpec(
        alias="opus-4.5",
        model_id="claude-opus-4-5-20251101",
        description="Older Opus snapshot.",
    ),
    "opus-4.1": ModelSpec(
        alias="opus-4.1",
        model_id="claude-opus-4-1-20250805",
        description="Older Opus snapshot.",
    ),
    "opus-4.0": ModelSpec(
        alias="opus-4.0",
        model_id="claude-opus-4-20250514",
        description="Legacy Claude 4 Opus snapshot.",
    ),
    "sonnet-4.6": ModelSpec(
        alias="sonnet-4.6",
        model_id="claude-sonnet-4-6",
        description="Latest Sonnet generation.",
        web_search_tool_type="web_search_20260209",
    ),
    "sonnet-4.5": ModelSpec(
        alias="sonnet-4.5",
        model_id="claude-sonnet-4-5-20250929",
        description="Older Sonnet snapshot.",
    ),
    "sonnet-4.0": ModelSpec(
        alias="sonnet-4.0",
        model_id="claude-sonnet-4-20250514",
        description="Legacy Claude 4 Sonnet snapshot.",
    ),
    "haiku-4.5": ModelSpec(
        alias="haiku-4.5",
        model_id="claude-haiku-4-5-20251001",
        description="Current Haiku model.",
    ),
}


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


def resolve_model(model_name: str) -> tuple[str, str]:
    spec = MODEL_SPECS.get(model_name)
    if spec:
        return spec.alias, spec.model_id
    return model_name, model_name


def resolve_web_search_tool_type(model_name: str, resolved_model: str) -> str:
    spec = MODEL_SPECS.get(model_name)
    if spec:
        return spec.web_search_tool_type
    if resolved_model in {"claude-opus-4-6", "claude-sonnet-4-6"}:
        return "web_search_20260209"
    return "web_search_20250305"


def read_required_text(path: Path, label: str) -> str:
    if not path.exists():
        raise AnthropicRunnerError(f"Missing {label}: {path}")
    return path.read_text(encoding="utf-8")


def build_user_message(
    macro_scan_text: str,
    writing_philosophy_text: str,
) -> str:
    return (
        "Use the files below as the complete working context.\n\n"
        "FILE: M1 macro scan/research-macro-scan.json\n"
        "```json\n"
        f"{macro_scan_text.strip()}\n"
        "```\n\n"
        "FILE: writing-phylosophy.jsx\n"
        "```jsx\n"
        f"{writing_philosophy_text.strip()}\n"
        "```\n\n"
        "Return only the final JSON object for "
        "`M2 Sector ranking/sector-ranking.json`. "
        "Do not wrap the answer in Markdown code fences and do not add commentary."
    )


def build_request_body(
    *,
    model: str,
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    temperature: float,
    enable_web_search: bool,
    web_search_tool_type: str,
    web_search_max_uses: int,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    messages = conversation_messages or [{"role": "user", "content": user_message}]
    body: dict[str, Any] = {
        "model": model,
        "system": system_prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if enable_web_search:
        body["tools"] = [
            {
                "type": web_search_tool_type,
                "name": "web_search",
                "max_uses": web_search_max_uses,
            }
        ]
    return body


def post_messages(
    *,
    api_key: str,
    body: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    request = Request(
        ANTHROPIC_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace").strip()
        raise AnthropicRunnerError(f"Anthropic HTTP {exc.code}: {payload[:500]}") from exc
    except URLError as exc:
        raise AnthropicRunnerError(f"Anthropic network error: {exc}") from exc
    except JSONDecodeError as exc:
        raise AnthropicRunnerError("Anthropic returned a non-JSON response.") from exc


def run_message_loop(
    *,
    api_key: str,
    body: dict[str, Any],
    timeout_seconds: int,
    max_pause_turns: int,
) -> dict[str, Any]:
    conversation_messages = list(body["messages"])
    final_response: dict[str, Any] | None = None

    for _ in range(max_pause_turns + 1):
        request_body = dict(body)
        request_body["messages"] = conversation_messages
        response = post_messages(
            api_key=api_key,
            body=request_body,
            timeout_seconds=timeout_seconds,
        )
        final_response = response
        if response.get("stop_reason") != "pause_turn":
            return response

        conversation_messages = conversation_messages + [
            {
                "role": "assistant",
                "content": response.get("content", []),
            }
        ]

    raise AnthropicRunnerError(
        "Anthropic response hit repeated pause_turn limits before producing a final answer."
    )


def extract_text_response(response: dict[str, Any]) -> str:
    parts: list[str] = []
    for block in response.get("content", []):
        if block.get("type") == "text":
            text = block.get("text", "")
            if text:
                parts.append(text)
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


def list_models() -> str:
    rows = []
    for spec in MODEL_SPECS.values():
        rows.append(f"{spec.alias:12} {spec.model_id:32} {spec.description}")
    return "\n".join(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the M2 sector ranking prompt with Anthropic Claude."
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_ALIAS,
        help="Model alias or raw Anthropic model ID. Use --list-models to see aliases.",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="Print supported model aliases and exit.",
    )
    parser.add_argument(
        "--prompt-file",
        default=str(DEFAULT_PROMPT_PATH),
        help="Path to the sector-ranking prompt markdown file.",
    )
    parser.add_argument(
        "--input-file",
        default=str(DEFAULT_INPUT_PATH),
        help="Path to the macro scan JSON input file.",
    )
    parser.add_argument(
        "--writing-file",
        default=str(DEFAULT_WRITING_PATH),
        help="Path to the Layer 1 writing philosophy file.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Where to write the final sector-ranking JSON output.",
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
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help="Maximum output tokens for the Anthropic response.",
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
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="HTTP timeout for each Anthropic API request.",
    )
    parser.add_argument(
        "--max-pause-turns",
        type=int,
        default=DEFAULT_MAX_PAUSE_TURNS,
        help="How many pause_turn continuations to allow for server tools.",
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

    if args.list_models:
        print(list_models())
        return

    prompt_path = Path(args.prompt_file)
    input_path = Path(args.input_file)
    writing_path = Path(args.writing_file)
    output_path = Path(args.output)
    raw_response_output = Path(args.raw_response_output) if args.raw_response_output else None

    requested_model, resolved_model = resolve_model(args.model)
    enable_web_search = not args.disable_web_search
    web_search_tool_type = resolve_web_search_tool_type(args.model, resolved_model)

    system_prompt = read_required_text(prompt_path, "prompt file")
    macro_scan_text = read_required_text(input_path, "macro input file")
    writing_philosophy_text = read_required_text(writing_path, "writing philosophy file")
    user_message = build_user_message(
        macro_scan_text=macro_scan_text,
        writing_philosophy_text=writing_philosophy_text,
    )

    request_body = build_request_body(
        model=resolved_model,
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        enable_web_search=enable_web_search,
        web_search_tool_type=web_search_tool_type,
        web_search_max_uses=args.web_search_max_uses,
    )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "requested_model": requested_model,
                    "resolved_model": resolved_model,
                    "prompt_file": str(prompt_path),
                    "input_file": str(input_path),
                    "writing_file": str(writing_path),
                    "output_file": str(output_path),
                    "web_search_enabled": enable_web_search,
                    "web_search_tool_type": web_search_tool_type if enable_web_search else None,
                    "web_search_max_uses": args.web_search_max_uses if enable_web_search else 0,
                    "max_tokens": args.max_tokens,
                    "temperature": args.temperature,
                },
                indent=2,
            )
        )
        return

    api_key = resolve_api_key(args.api_key)
    response = run_message_loop(
        api_key=api_key,
        body=request_body,
        timeout_seconds=args.timeout_seconds,
        max_pause_turns=args.max_pause_turns,
    )
    response_text = extract_text_response(response)
    payload = parse_json_payload(response_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if raw_response_output:
        raw_response_output.parent.mkdir(parents=True, exist_ok=True)
        raw_response_output.write_text(
            json.dumps(response, indent=2) + "\n",
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "output_file": str(output_path),
                "requested_model": requested_model,
                "resolved_model": resolved_model,
                "stop_reason": response.get("stop_reason"),
                "usage": response.get("usage", {}),
                "web_search_enabled": enable_web_search,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
