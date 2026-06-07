"""llama-cpp GGUF judge backend (in-process generative, CPU, no GPU).

Weights (a quantized GGUF) are downloaded from the Hugging Face Hub on first use
and cached. Config: ``model`` = HF repo id, ``file`` = GGUF filename in that repo.

NOTE: depends on the optional ``[llama]`` extra and a downloaded model, so the
real run cannot be exercised here; the wrapper is unit-tested by mocking
:func:`_complete`. Sync only -- aseal() falls back to running it via the sync
path (build_ajudge returns None for this runtime).
"""

from __future__ import annotations

from typing import Any

from ..errors import BulkheadConfigError
from ..types import BulkheadConfig, JudgeScorer
from . import registry
from .base import JUDGE_PROMPT, join_chunks, parse_judge_json

_MODELS: dict[tuple[str, str], Any] = {}


def _load(repo_id: str, filename: str):
    key = (repo_id, filename)
    if key in _MODELS:
        return _MODELS[key]
    from huggingface_hub import hf_hub_download  # type: ignore
    from llama_cpp import Llama  # type: ignore

    path = hf_hub_download(repo_id, filename)
    llm = Llama(model_path=path, n_ctx=4096, verbose=False)
    _MODELS[key] = llm
    return llm


def _complete(repo_id: str, filename: str, system: str, user: str) -> str:
    llm = _load(repo_id, filename)
    out = llm.create_chat_completion(
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return out["choices"][0]["message"]["content"] or ""


def llama_judge_factory(spec: dict[str, Any], _config: BulkheadConfig) -> JudgeScorer:
    repo_id = spec.get("model")
    filename = spec.get("file")
    if not repo_id or not filename:
        raise BulkheadConfigError(
            "llama_cpp judge requires 'model' (HF repo id) and 'file' (GGUF filename)"
        )

    def judge(chunks: list[str]) -> Any:
        text = _complete(repo_id, filename, JUDGE_PROMPT, join_chunks(chunks))
        return parse_judge_json(text)

    return judge


def prepare(repo_id: str, filename: str) -> None:
    """Download + smoke-test (used by `bulkhead setup`)."""
    _complete(repo_id, filename, JUDGE_PROMPT, "smoke test")


registry.register_judge("llama_cpp", llama_judge_factory)
