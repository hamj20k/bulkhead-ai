"""Ollama judge backend (local generative model, served by Ollama).

Talks to the Ollama HTTP API over the stdlib (urllib), so the ``[ollama]`` path
needs no extra Python dependency. Exposes sync + async judges. The async judge
offloads the blocking HTTP call to a thread so aseal() never blocks the loop.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any, Callable

from ..errors import BulkheadConfigError
from ..types import AsyncJudgeScorer, BulkheadConfig, JudgeScorer
from . import registry
from .base import JUDGE_PROMPT, join_chunks, parse_judge_json

DEFAULT_BASE_URL = "http://localhost:11434"


def _chat(base_url: str, model: str, system: str, user: str, timeout: float) -> str:
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("message", {}).get("content", "")


def _prep(spec: dict[str, Any], config: BulkheadConfig):
    model = spec.get("model")
    if not model:
        raise BulkheadConfigError("ollama judge requires 'model' in config")
    base_url = spec.get("base_url") or DEFAULT_BASE_URL
    return model, base_url, config.judge_timeout


def ollama_judge_factory(spec: dict[str, Any], config: BulkheadConfig) -> JudgeScorer:
    model, base_url, timeout = _prep(spec, config)

    def judge(chunks: list[str]) -> Any:
        text = _chat(base_url, model, JUDGE_PROMPT, join_chunks(chunks), timeout)
        return parse_judge_json(text)

    return judge


def ollama_ajudge_factory(spec: dict[str, Any], config: BulkheadConfig) -> AsyncJudgeScorer:
    model, base_url, timeout = _prep(spec, config)

    async def ajudge(chunks: list[str]) -> Any:
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(
            None, _chat, base_url, model, JUDGE_PROMPT, join_chunks(chunks), timeout
        )
        return parse_judge_json(text)

    return ajudge


# --- CLI helpers -------------------------------------------------------------


def is_available(base_url: str = DEFAULT_BASE_URL, timeout: float = 2.0) -> bool:
    """True if an Ollama daemon answers at base_url."""
    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=timeout):
            return True
    except (urllib.error.URLError, OSError):
        return False


def pull(
    model: str,
    base_url: str = DEFAULT_BASE_URL,
    progress: Callable[[str, int, int], None] | None = None,
) -> None:
    """Pull a model via Ollama, streaming progress to the callback as
    (status, completed_bytes, total_bytes)."""
    body = json.dumps({"name": model, "stream": True}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/pull",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        for line in resp:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line.decode("utf-8"))
            if progress is not None:
                progress(
                    event.get("status", ""),
                    int(event.get("completed", 0) or 0),
                    int(event.get("total", 0) or 0),
                )


registry.register_judge("ollama", ollama_judge_factory)
registry.register_ajudge("ollama", ollama_ajudge_factory)
