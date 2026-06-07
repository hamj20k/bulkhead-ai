"""Cloud (hosted API) judge backend: OpenAI / Groq / OpenAI-compatible / Anthropic.

Exposes both a sync and an async judge so ``seal()`` and ``aseal()`` each get a
native path. The API key is read from the environment variable named in the
config (``key_env``); the key itself is never stored in config.

PRIVACY: a cloud judge sends the retrieved content to the chosen provider. This
is disclosed by `bulkhead setup` and in the docs.
"""

from __future__ import annotations

import os
from typing import Any

from ..errors import BulkheadConfigError
from ..types import AsyncJudgeScorer, BulkheadConfig, JudgeScorer
from . import registry
from .base import JUDGE_PROMPT, join_chunks, parse_judge_json

_DEFAULT_MODEL = {
    "openai": "gpt-4o-mini",
    "groq": "llama-3.1-8b-instant",
    "compatible": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
}
_DEFAULT_BASE_URL = {"groq": "https://api.groq.com/openai/v1"}
_OPENAI_LIKE = ("openai", "groq", "compatible")
_MAX_TOKENS = 256


def _get_key(spec: dict[str, Any]) -> str:
    key_env = spec.get("key_env")
    if not key_env:
        raise BulkheadConfigError("cloud judge requires 'key_env' in config")
    key = os.environ.get(key_env)
    if not key:
        raise BulkheadConfigError(
            f"environment variable {key_env!r} is not set (cloud judge API key)"
        )
    return key


def _prep(spec: dict[str, Any], config: BulkheadConfig):
    provider = (spec.get("provider") or "openai").lower()
    if provider not in _OPENAI_LIKE and provider != "anthropic":
        raise BulkheadConfigError(f"unknown cloud provider {provider!r}")
    model = spec.get("model") or _DEFAULT_MODEL[provider]
    base_url = spec.get("base_url") or _DEFAULT_BASE_URL.get(provider)
    return provider, model, base_url, _get_key(spec), config.judge_timeout


# --- provider calls (lazy SDK imports; monkeypatched in tests) ---------------


def _invoke_sync(provider, model, system, user, key, base_url, timeout) -> str:
    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=key, timeout=timeout)
        resp = client.messages.create(
            model=model,
            system=system,
            max_tokens=_MAX_TOKENS,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
        )
    import openai

    client = openai.OpenAI(api_key=key, base_url=base_url, timeout=timeout)
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


async def _invoke_async(provider, model, system, user, key, base_url, timeout) -> str:
    if provider == "anthropic":
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=key, timeout=timeout)
        resp = await client.messages.create(
            model=model,
            system=system,
            max_tokens=_MAX_TOKENS,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
        )
    import openai

    client = openai.AsyncOpenAI(api_key=key, base_url=base_url, timeout=timeout)
    resp = await client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


# --- factories ----------------------------------------------------------------


def cloud_judge_factory(spec: dict[str, Any], config: BulkheadConfig) -> JudgeScorer:
    provider, model, base_url, key, timeout = _prep(spec, config)

    def judge(chunks: list[str]) -> Any:
        text = _invoke_sync(
            provider, model, JUDGE_PROMPT, join_chunks(chunks), key, base_url, timeout
        )
        return parse_judge_json(text)

    return judge


def cloud_ajudge_factory(spec: dict[str, Any], config: BulkheadConfig) -> AsyncJudgeScorer:
    provider, model, base_url, key, timeout = _prep(spec, config)

    async def ajudge(chunks: list[str]) -> Any:
        text = await _invoke_async(
            provider, model, JUDGE_PROMPT, join_chunks(chunks), key, base_url, timeout
        )
        return parse_judge_json(text)

    return ajudge


registry.register_judge("cloud", cloud_judge_factory)
registry.register_ajudge("cloud", cloud_ajudge_factory)
