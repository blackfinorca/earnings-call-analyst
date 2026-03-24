from __future__ import annotations

import os
import random
import time
from pathlib import Path

import anthropic


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


def resolve_api_key(explicit_api_key: str | None, env_var: str, error_cls: type[Exception]) -> str:
    if explicit_api_key:
        return explicit_api_key
    api_key = os.getenv(env_var)
    if api_key:
        return api_key
    raise error_cls(f"Missing {env_var}. Set it in .env or export it in the shell.")


def read_required_text(path: Path, label: str, error_cls: type[Exception]) -> str:
    if not path.exists():
        raise error_cls(f"Missing {label}: {path}")
    return path.read_text(encoding="utf-8")


def stream_with_retry(
    *,
    client: anthropic.Anthropic,
    model: str,
    system_prompt: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    max_retries: int,
    base_delay: float,
    max_delay: float,
    error_cls: type[Exception],
    tools: list[dict] | None = None,
) -> anthropic.types.Message:
    kwargs: dict = {
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
                raise
            last_exc = exc
            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
        except anthropic.APIConnectionError as exc:
            last_exc = exc
            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)

        print(f"\n[Retry {attempt + 1}/{max_retries}] Waiting {delay:.1f}s before retrying...", flush=True)
        time.sleep(delay)

    raise error_cls(f"Anthropic request failed after {max_retries} retries.") from last_exc


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
    error_cls: type[Exception] = RuntimeError,
    tools: list[dict] | None = None,
) -> anthropic.types.Message:
    messages: list[dict] = [{"role": "user", "content": user_message}]

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
            error_cls=error_cls,
            tools=tools,
        )
        if response.stop_reason != "pause_turn":
            return response
        messages = messages + [{"role": "assistant", "content": response.content}]

    raise error_cls("Anthropic response hit repeated pause_turn limits before producing a final answer.")


def extract_text_response(response) -> str:
    parts: list[str] = []
    for block in response.content:
        if getattr(block, "type", None) == "text" and getattr(block, "text", None):
            parts.append(block.text)
    return "\n".join(parts).strip()
