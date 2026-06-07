"""Runtime registry: maps a config ``runtime`` to a factory that builds a gate
scorer or a cross-chunk judge callable.

Built-in (dependency-free) runtimes are handled directly:
- gate ``regex`` / missing  -> ``None`` (core uses the default regex scorer)
- gate ``none``             -> a zero-risk scorer (gate disabled)
- judge ``none`` / missing  -> ``None`` (no judge)

Model runtimes (``onnx``, ``ollama``, ``llama_cpp``, ``transformers``, ``cloud``)
register a factory by importing their module. If a config references a runtime
whose backend has not been imported/installed, building raises a clear error
pointing at the matching extra.
"""

from __future__ import annotations

from typing import Any, Callable

from ..errors import BulkheadConfigError
from ..types import AnyJudge, AnyScorer, BulkheadConfig, RiskResult

GateFactory = Callable[[dict, BulkheadConfig], AnyScorer]
JudgeFactory = Callable[[dict, BulkheadConfig], AnyJudge]

_GATE_FACTORIES: dict[str, GateFactory] = {}
_JUDGE_FACTORIES: dict[str, JudgeFactory] = {}
_AJUDGE_FACTORIES: dict[str, JudgeFactory] = {}

# Map runtime -> the extra to install, for helpful error messages.
_EXTRA_FOR_RUNTIME = {
    "onnx": "onnx",
    "llama_cpp": "llama",
    "transformers": "transformers",
    "ollama": "ollama",
    "cloud": "openai",  # or anthropic; setup picks per provider
}


def register_gate(runtime: str, factory: GateFactory) -> None:
    _GATE_FACTORIES[runtime] = factory


def register_judge(runtime: str, factory: JudgeFactory) -> None:
    _JUDGE_FACTORIES[runtime] = factory


def register_ajudge(runtime: str, factory: JudgeFactory) -> None:
    _AJUDGE_FACTORIES[runtime] = factory


def _zero_scorer(_content: str) -> RiskResult:
    return RiskResult(score=0.0, flags=[], confidence="low", raw_matches=[])


def _missing(runtime: str, role: str) -> BulkheadConfigError:
    extra = _EXTRA_FOR_RUNTIME.get(runtime, runtime)
    return BulkheadConfigError(
        f"{role} runtime {runtime!r} is not available. Install the matching extra: "
        f"pip install 'bulkhead-ai[{extra}]', then run `bulkhead setup` again."
    )


def build_gate(spec: dict[str, Any] | None, config: BulkheadConfig) -> AnyScorer | None:
    if not spec:
        return None
    runtime = (spec.get("runtime") or "regex").lower()
    if runtime in ("regex", ""):
        return None
    if runtime == "none":
        return _zero_scorer
    factory = _GATE_FACTORIES.get(runtime)
    if factory is None:
        raise _missing(runtime, "gate")
    return factory(spec, config)


def build_judge(spec: dict[str, Any] | None, config: BulkheadConfig) -> AnyJudge | None:
    if not spec:
        return None
    runtime = (spec.get("runtime") or "none").lower()
    if runtime in ("none", ""):
        return None
    factory = _JUDGE_FACTORIES.get(runtime)
    if factory is None:
        raise _missing(runtime, "judge")
    return factory(spec, config)


def build_ajudge(spec: dict[str, Any] | None, config: BulkheadConfig) -> AnyJudge | None:
    """Async-native judge for aseal(). Returns None (graceful fallback to the
    sync judge) when the runtime has no async factory."""
    if not spec:
        return None
    runtime = (spec.get("runtime") or "none").lower()
    if runtime in ("none", ""):
        return None
    factory = _AJUDGE_FACTORIES.get(runtime)
    if factory is None:
        return None
    return factory(spec, config)
