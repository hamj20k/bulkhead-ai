"""transformers (PyTorch) encoder-classifier gate (per-chunk).

The flexible-but-heavy local gate: runs a text-classification model via the
`transformers` pipeline (pulls torch). Prefer the `onnx` runtime for a lighter
footprint; this exists for models that aren't exported to ONNX.

NOTE: depends on the optional `[transformers]` extra and a downloaded model, so
the real run can't be exercised here; the wrapper is unit-tested by mocking
:func:`_infer`.
"""

from __future__ import annotations

from typing import Any

from ..types import BulkheadConfig, RiskResult, Scorer
from . import registry

DEFAULT_MODEL = "protectai/deberta-v3-base-prompt-injection-v2"
_PIPELINES: dict[str, Any] = {}


def _load(model_id: str):
    if model_id in _PIPELINES:
        return _PIPELINES[model_id]
    from transformers import pipeline  # type: ignore

    _PIPELINES[model_id] = pipeline("text-classification", model=model_id, truncation=True)
    return _PIPELINES[model_id]


def _infer(model_id: str, text: str) -> float:
    """Return P(injection) in [0, 1] for one chunk."""
    out = _load(model_id)(text)
    row = out[0] if isinstance(out, list) else out
    label = str(row.get("label", "")).upper()
    score = float(row.get("score", 0.0))
    is_injection = "INJECT" in label or label in ("LABEL_1", "1", "UNSAFE", "TOXIC")
    return score if is_injection else 1.0 - score


def transformers_gate_factory(spec: dict[str, Any], _config: BulkheadConfig) -> Scorer:
    model_id = spec.get("model") or DEFAULT_MODEL

    def gate(content: str) -> RiskResult:
        p = _infer(model_id, content)
        confidence = "high" if p >= 0.7 else "medium" if p >= 0.3 else "low"
        flags = ["encoder_injection"] if p >= 0.5 else []
        return RiskResult(score=round(p, 2), flags=flags, confidence=confidence, raw_matches=[])

    return gate


def prepare(model_id: str = DEFAULT_MODEL) -> None:
    _PIPELINES.pop(model_id, None)
    _infer(model_id, "smoke test")


registry.register_gate("transformers", transformers_gate_factory)
