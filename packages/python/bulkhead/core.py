from __future__ import annotations

from typing import Tuple

from .errors import BulkheadConfigError
from .gate import enforce
from .renderer import GUARD, generate_nonce, render_json_payload
from .scorer import score
from .types import BulkheadConfig, RiskResult, Scorer, SealOutput

_VALID_POLICIES = ("strict", "warn", "permissive")


def _validate(config: BulkheadConfig) -> None:
    if config.policy not in _VALID_POLICIES:
        raise BulkheadConfigError(
            f"policy must be one of {_VALID_POLICIES}, got {config.policy!r}"
        )
    threshold = config.scorer.threshold
    if not (0.0 <= threshold <= 1.0):
        raise BulkheadConfigError(
            f"scorer.threshold must be between 0.0 and 1.0, got {threshold}"
        )


def _resolve_scorer(config: BulkheadConfig, scorer: Scorer | None) -> Scorer:
    """The built-in regex scorer is the default; any callable
    ``(content: str) -> RiskResult`` can replace it (e.g. an LLM judge)."""
    if scorer is not None:
        return scorer
    return lambda content: score(content, config.scorer)


def _normalize_sources(retrieved: str | list[str]) -> list[str]:
    sources = retrieved if isinstance(retrieved, list) else [retrieved]
    return [source for source in sources if source.strip()]


def _aggregate_risks(results: list[RiskResult]) -> RiskResult:
    if not results:
        return RiskResult(score=0.0, flags=[], confidence="low", raw_matches=[])
    flags: list[str] = []
    raw_matches: list[str] = []
    max_result = results[0]
    for result in results:
        if result.score > max_result.score:
            max_result = result
        for flag in result.flags:
            if flag not in flags:
                flags.append(flag)
        raw_matches.extend(result.raw_matches)
    return RiskResult(
        score=max_result.score,
        flags=flags,
        confidence=max_result.confidence,
        raw_matches=raw_matches,
    )


def _seal_with_risk(
    user: str,
    retrieved: str | list[str],
    config: BulkheadConfig,
    scorer: Scorer | None = None,
) -> Tuple[SealOutput, RiskResult]:
    """Score once, gate, wrap. Returns both the output and the risk result so
    callers (e.g. sessions) never need to re-score."""
    sources = _normalize_sources(retrieved)
    scorer_fn = _resolve_scorer(config, scorer)
    risk_results = [scorer_fn(source) for source in sources]
    risk_result = _aggregate_risks(risk_results)
    enforce(risk_result, config)
    data = (
        render_json_payload(user, sources, risk_results, generate_nonce())
        if sources
        else ""
    )
    sealed = SealOutput(
        instruction=user,
        data=data,
        guard=GUARD if data else "",
    )
    return sealed, risk_result


def seal(
    user: str,
    retrieved: str | list[str],
    config: BulkheadConfig | None = None,
    scorer: Scorer | None = None,
) -> SealOutput:
    """Separate the trusted USER instruction from untrusted RETRIEVED content.

    Returns a :class:`SealOutput` whose ``prompt`` is the untouched user
    instruction and whose ``data`` is a JSON payload containing
    ``trusted_instruction`` and ``untrusted_inputs``. The return shape is
    identical across all policy modes.

    Pass ``scorer`` to swap the built-in regex scorer for your own callable.
    """
    cfg = config or BulkheadConfig()
    _validate(cfg)
    sealed, _ = _seal_with_risk(user, retrieved, cfg, scorer)
    return sealed


class BulkheadSession:
    """Multi-turn session. Accumulates risk history for observability.

    Each turn is scored and gated independently -- the session does not change
    gating behavior across turns (track-only).
    """

    def __init__(
        self,
        config: BulkheadConfig | None = None,
        scorer: Scorer | None = None,
    ):
        self.config = config or BulkheadConfig()
        _validate(self.config)
        self._scorer = scorer
        self.risk_history: list[RiskResult] = []

    def seal(self, user: str, retrieved: str | list[str]) -> SealOutput:
        sealed, risk = _seal_with_risk(user, retrieved, self.config, self._scorer)
        self.risk_history.append(risk)
        return sealed

    def reset(self) -> None:
        self.risk_history = []


class Bulkhead:
    """Configured entry point for sealing content.

    ``scorer`` is an optional callable ``(content: str) -> RiskResult`` that
    replaces the built-in regex scorer (e.g. an LLM-based judge or a hosted
    detector). The built-in regex scorer is a cheap heuristic pre-filter, not
    the security boundary -- the structural separation is.
    """

    def __init__(
        self,
        config: BulkheadConfig | None = None,
        scorer: Scorer | None = None,
    ):
        self.config = config or BulkheadConfig()
        _validate(self.config)
        self._scorer = scorer

    def seal(self, user: str, retrieved: str | list[str]) -> SealOutput:
        return seal(user, retrieved, self.config, self._scorer)

    def session(self) -> BulkheadSession:
        return BulkheadSession(config=self.config, scorer=self._scorer)
