"""
LLM client abstraction shared by all REMY sub-agents.

Model routing:
  - "claude-*"  → Anthropic API (needs ANTHROPIC_API_KEY)
  - "ollama:<name>" → local Ollama server (OLLAMA_URL) — used to keep the
    Watcher's routine heartbeat checks free/cheap
If neither is available, LLMUnavailable is raised and callers degrade to
their coded fallbacks (the heartbeat still runs rule-based checks).
"""

import base64
import json
from typing import Any

import httpx

from remy.config import config


class LLMUnavailable(RuntimeError):
    pass


def _anthropic_client():
    if not config.ANTHROPIC_API_KEY:
        raise LLMUnavailable("ANTHROPIC_API_KEY not set")
    try:
        import anthropic
    except ImportError as exc:
        raise LLMUnavailable('anthropic SDK missing: pip install "remy[llm]"') from exc
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def _ollama_complete(model: str, system: str, messages: list[dict],
                     temperature: float) -> str:
    prompt_messages = [{"role": "system", "content": system}] + [
        {"role": m["role"],
         "content": m["content"] if isinstance(m["content"], str)
         else json.dumps(m["content"])}
        for m in messages
    ]
    try:
        r = httpx.post(
            f"{config.OLLAMA_URL}/api/chat",
            json={"model": model, "messages": prompt_messages,
                  "stream": False, "options": {"temperature": temperature}},
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["message"]["content"]
    except (httpx.HTTPError, KeyError) as exc:
        raise LLMUnavailable(f"Ollama unreachable at {config.OLLAMA_URL}: {exc}") from exc


def complete(model: str, system: str, messages: list[dict],
             max_tokens: int = 2048, temperature: float = 0.7) -> str:
    """Plain text completion (no tools)."""
    if model.startswith("ollama:"):
        return _ollama_complete(model.split(":", 1)[1], system, messages, temperature)
    client = _anthropic_client()
    resp = client.messages.create(
        model=model, system=system, messages=messages,
        max_tokens=max_tokens, temperature=temperature,
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def complete_with_tools(model: str, system: str, messages: list[dict],
                        tools: list[dict], max_tokens: int = 2048,
                        temperature: float = 0.7) -> Any:
    """One tool-use-capable turn; returns the raw Anthropic response."""
    client = _anthropic_client()
    return client.messages.create(
        model=model, system=system, messages=messages, tools=tools,
        max_tokens=max_tokens, temperature=temperature,
    )


def stream_with_tools(model: str, system: str, messages: list[dict],
                      tools: list[dict], max_tokens: int = 2048,
                      temperature: float = 0.7):
    """
    One tool-use-capable turn, streamed. Yields ("text", delta) for each text
    delta as it arrives, then a final ("final", message) carrying the complete
    assistant message (including any tool_use blocks). Ollama models don't
    support this tool-streaming path, so callers should use it only for the
    Anthropic-backed orchestrator.
    """
    client = _anthropic_client()
    with client.messages.stream(
        model=model, system=system, messages=messages, tools=tools,
        max_tokens=max_tokens, temperature=temperature,
    ) as stream:
        for delta in stream.text_stream:
            yield ("text", delta)
        final = stream.get_final_message()
    yield ("final", final)


def describe_image(path: str, prompt: str = "Describe what is visible on this screen, concisely.") -> str:
    """Vision call used by the describe_screen tool."""
    client = _anthropic_client()
    data = base64.standard_b64encode(open(path, "rb").read()).decode()
    resp = client.messages.create(
        model=config.EXECUTOR_MODEL,
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": "image/png",
                                             "data": data}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    return "".join(b.text for b in resp.content if b.type == "text")
