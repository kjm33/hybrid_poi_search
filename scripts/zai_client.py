"""Shared OpenAI-compatible chat client for the amenity enrichment pipeline.

Two backends, selected via env var LLM_BASE:
- unset or "zai"      → z.ai GLM Coding Plan (key from ~/.local/share/opencode/auth.json,
                        endpoint https://api.z.ai/api/coding/paas/v4, OpenAI-compatible)
- "vllm" or a URL     → local vLLM server (default http://localhost:8000/v1, dummy key;
                        set LLM_BASE=http://host:port/v1 to override)

Both z.ai GLM models are reasoning models: the answer is in message.content,
chain-of-thought in message.reasoning_content (ignored here); max_tokens must
cover reasoning + answer or content comes back truncated/empty.
"""
from __future__ import annotations

import json
import os
import pathlib
import time
import urllib.error
import urllib.request

ZAI_BASE = "https://api.z.ai/api/coding/paas/v4/chat/completions"


def _base_and_key() -> tuple[str, str]:
    base_env = os.environ.get("LLM_BASE", "zai")
    if base_env in ("zai", ""):
        auth = json.loads((pathlib.Path.home() / ".local/share/opencode/auth.json").read_text())
        return ZAI_BASE, auth["zai-coding-plan"]["key"]
    url = base_env if base_env.startswith("http") else "http://localhost:8000/v1"
    return url.rstrip("/") + "/chat/completions", os.environ.get("LLM_API_KEY", "dummy")


BASE, _KEY = _base_and_key()
TOTAL_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}


class RateLimited(RuntimeError):
    """Raised when the plan's request-rate limit (HTTP 429 / code 1302) persists
    through all retries. Callers should pause and retry later, not blame the input."""


def chat(
    model: str,
    messages: list[dict],
    max_tokens: int = 8192,
    temperature: float = 0.1,
    retries: int = 6,
    timeout: int = 180,
) -> tuple[str, dict]:
    """Call GLM. Returns (content, usage). Retries with backoff on 429/5xx/network."""
    payload = json.dumps(
        {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    ).encode()
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(
            BASE, data=payload, headers={"Authorization": f"Bearer {_KEY}", "Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                r = json.loads(resp.read())
            usage = r.get("usage", {})
            TOTAL_USAGE["prompt_tokens"] += usage.get("prompt_tokens", 0)
            TOTAL_USAGE["completion_tokens"] += usage.get("completion_tokens", 0)
            TOTAL_USAGE["calls"] += 1
            return r["choices"][0]["message"]["content"] or "", usage
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.read()[:200]!r}"
            if e.code == 429:
                time.sleep(min(30 * (attempt + 1), 150))  # rate limit: wait it out
            elif e.code in (500, 502, 503, 504):
                time.sleep(min(2**attempt * 2, 60))
            else:
                raise
        except Exception as e:  # network hiccups
            last_err = repr(e)
            time.sleep(min(2**attempt * 2, 60))
    if "HTTP 429" in str(last_err):
        raise RateLimited(f"chat failed after {retries} retries: {last_err}")
    raise RuntimeError(f"chat failed after {retries} retries: {last_err}")


def usage_report() -> str:
    t = TOTAL_USAGE
    return (
        f"{t['calls']} calls, {t['prompt_tokens']:,} prompt tokens, "
        f"{t['completion_tokens']:,} completion tokens"
    )
