from __future__ import annotations

import hashlib
import inspect
import warnings
from typing import Any, Awaitable, Tuple

from .errors import BulkheadConfigError
from .gate import enforce
from .renderer import GUARD, generate_nonce, render_json_payload
from .scorer import score
from .types import (
    AnyJudge,
    AnyScorer,
    BulkheadConfig,
    RiskResult,
    Scorer,
    SealOutput,
)

_VALID_POLICIES = ("strict", "warn", "permissive")

# Process-local cache of judge verdicts, keyed by (judge identity, content hash).
# The judge is the expensive tier and the same chunks recur across RAG queries.
_JUDGE_CACHE: dict[str, RiskResult] = {}
_JUDGE_CACHE_CAP = 1024


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


def _resolve_scorer(config: BulkheadConfig, scorer: AnyScorer | None) -> AnyScorer:
    """The built-in regex scorer is the default; any callable
    ``(content: str) -> RiskResult`` (sync or async) can replace it."""
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


# --- cross-chunk judge escalation -------------------------------------------


def _gate_flagged(results: list[RiskResult], threshold: float) -> bool:
    return any(r.flags or r.score >= threshold for r in results)


def _should_judge(
    config: BulkheadConfig,
    per_chunk: list[RiskResult],
    sources: list[str],
) -> bool:
    """Decide whether the cross-chunk judge should run. Pure (no I/O), so the
    sync and async seal paths share it."""
    when = config.judge_when
    if when == "never":
        return False
    if when == "always":
        return True
    if when == "gate_flagged":
        return _gate_flagged(per_chunk, config.scorer.threshold)
    # suspicious_or_many: any gate flag, OR many chunks, OR a cheap combined-text
    # regex pre-pass trips (the only trigger that catches pure cross-chunk splits,
    # since those leave every individual chunk looking benign).
    if _gate_flagged(per_chunk, config.scorer.threshold):
        return True
    if len(sources) >= config.judge_min_chunks:
        return True
    combined = "\n\n".join(sources)
    return bool(score(combined, config.scorer).flags)


def _resolve_on_error(config: BulkheadConfig) -> str:
    if config.judge_on_error != "auto":
        return config.judge_on_error
    return "fail_closed" if config.policy == "strict" else "fail_open"


def _handle_judge_error(exc: Exception, config: BulkheadConfig) -> RiskResult | None:
    """Apply judge_on_error. NEVER silent: always warn. Returns None to skip the
    judge (fail_open) or a max-risk result so policy applies (fail_closed)."""
    mode = _resolve_on_error(config)
    warnings.warn(
        f"[bulkhead] judge backend error ({type(exc).__name__}: {exc}). "
        f"Applying judge_on_error={mode!r}.",
        UserWarning,
        stacklevel=3,
    )
    if mode == "fail_open":
        return None
    return RiskResult(
        score=1.0, flags=["judge_unavailable"], confidence="high", raw_matches=[]
    )


def _judge_cache_key(judge: AnyJudge, sources: list[str]) -> str:
    digest = hashlib.sha256("\x00".join(sources).encode("utf-8")).hexdigest()
    return f"{id(judge)}:{digest}"


def _cache_get(key: str) -> RiskResult | None:
    return _JUDGE_CACHE.get(key)


def _cache_put(key: str, result: RiskResult) -> None:
    if len(_JUDGE_CACHE) >= _JUDGE_CACHE_CAP:
        _JUDGE_CACHE.clear()
    _JUDGE_CACHE[key] = result


def _run_judge_sync(
    judge: AnyJudge, sources: list[str], config: BulkheadConfig
) -> RiskResult | None:
    key = _judge_cache_key(judge, sources)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    try:
        result = judge(sources)
    except Exception as exc:  # noqa: BLE001 -- failure mode is explicit/configurable
        return _handle_judge_error(exc, config)
    # Misuse (async judge in the sync path) is a programming error, not a backend
    # failure: raise clearly instead of routing through judge_on_error.
    if inspect.isawaitable(result):
        if hasattr(result, "close"):
            result.close()
        raise TypeError(
            "async judge passed to sync seal(); use aseal() for async judges"
        )
    _cache_put(key, result)
    return result


async def _run_judge_async(
    judge: AnyJudge, sources: list[str], config: BulkheadConfig
) -> RiskResult | None:
    key = _judge_cache_key(judge, sources)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    try:
        result = judge(sources)
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:  # noqa: BLE001
        return _handle_judge_error(exc, config)
    assert isinstance(result, RiskResult)
    _cache_put(key, result)
    return result


def _assemble(
    user: str,
    sources: list[str],
    per_chunk: list[RiskResult],
    results: list[RiskResult],
    config: BulkheadConfig,
) -> Tuple[SealOutput, RiskResult]:
    risk = _aggregate_risks(results)
    enforce(risk, config)
    data = (
        render_json_payload(user, sources, per_chunk, generate_nonce())
        if sources
        else ""
    )
    sealed = SealOutput(
        instruction=user,
        data=data,
        guard=GUARD if data else "",
    )
    return sealed, risk


def _seal_with_risk(
    user: str,
    retrieved: str | list[str],
    config: BulkheadConfig,
    scorer: AnyScorer | None = None,
    judge: AnyJudge | None = None,
) -> Tuple[SealOutput, RiskResult]:
    """Score (gate per chunk), optionally escalate to the cross-chunk judge, gate,
    wrap. Returns both the output and the risk so callers never re-score."""
    sources = _normalize_sources(retrieved)
    gate_fn = _resolve_scorer(config, scorer)
    per_chunk: list[RiskResult] = []
    for source in sources:
        result = gate_fn(source)
        if inspect.isawaitable(result):
            raise TypeError(
                "async scorer passed to sync seal(); use aseal() for async scorers"
            )
        per_chunk.append(result)
    results = list(per_chunk)
    if judge is not None and sources and _should_judge(config, per_chunk, sources):
        judge_result = _run_judge_sync(judge, sources, config)
        if judge_result is not None:
            results.append(judge_result)
    return _assemble(user, sources, per_chunk, results, config)


async def _aseal_with_risk(
    user: str,
    retrieved: str | list[str],
    config: BulkheadConfig,
    scorer: AnyScorer | None = None,
    judge: AnyJudge | None = None,
) -> Tuple[SealOutput, RiskResult]:
    """Async-native twin of _seal_with_risk: gate and judge calls are awaited."""
    sources = _normalize_sources(retrieved)
    gate_fn = _resolve_scorer(config, scorer)
    per_chunk: list[RiskResult] = []
    for source in sources:
        result: Any = gate_fn(source)
        if inspect.isawaitable(result):
            result = await result
        per_chunk.append(result)
    results = list(per_chunk)
    if judge is not None and sources and _should_judge(config, per_chunk, sources):
        judge_result = await _run_judge_async(judge, sources, config)
        if judge_result is not None:
            results.append(judge_result)
    return _assemble(user, sources, per_chunk, results, config)


def seal(
    user: str,
    retrieved: str | list[str],
    config: BulkheadConfig | None = None,
    scorer: AnyScorer | None = None,
    judge: AnyJudge | None = None,
) -> SealOutput:
    """Separate the trusted USER instruction from untrusted RETRIEVED content.

    Returns a :class:`SealOutput` whose ``prompt`` is the untouched user
    instruction and whose ``data`` is a JSON payload containing
    ``trusted_instruction`` and ``untrusted_inputs``. The return shape is
    identical across all policy modes.

    Pass ``scorer`` to swap the built-in per-chunk regex scorer, and ``judge``
    for a cross-chunk judge (run per ``config.judge_when``). For async judges/
    scorers in an asyncio server, use :func:`aseal` instead so the event loop is
    never blocked.
    """
    cfg = config or BulkheadConfig()
    _validate(cfg)
    sealed, _ = _seal_with_risk(user, retrieved, cfg, scorer, judge)
    return sealed


async def aseal(
    user: str,
    retrieved: str | list[str],
    config: BulkheadConfig | None = None,
    scorer: AnyScorer | None = None,
    judge: AnyJudge | None = None,
) -> SealOutput:
    """Async-native companion to :func:`seal` for asyncio servers (FastAPI,
    Starlette, ...). Identical behavior and output; the only difference is that
    scorer/judge backend calls are awaited natively instead of run blocking, so
    the event loop is never blocked on a cloud/Ollama judge call. ``seal()`` is
    unchanged and remains the default for synchronous code.
    """
    cfg = config or BulkheadConfig()
    _validate(cfg)
    sealed, _ = await _aseal_with_risk(user, retrieved, cfg, scorer, judge)
    return sealed


class BulkheadSession:
    """Multi-turn session. Accumulates risk history for observability.

    Each turn is scored and gated independently -- the session does not change
    gating behavior across turns (track-only).
    """

    def __init__(
        self,
        config: BulkheadConfig | None = None,
        scorer: AnyScorer | None = None,
        judge: AnyJudge | None = None,
        ajudge: AnyJudge | None = None,
    ):
        self.config = config or BulkheadConfig()
        _validate(self.config)
        self._scorer = scorer
        self._judge = judge
        self._ajudge = ajudge
        self.risk_history: list[RiskResult] = []

    def seal(self, user: str, retrieved: str | list[str]) -> SealOutput:
        sealed, risk = _seal_with_risk(
            user, retrieved, self.config, self._scorer, self._judge
        )
        self.risk_history.append(risk)
        return sealed

    async def aseal(self, user: str, retrieved: str | list[str]) -> SealOutput:
        sealed, risk = await _aseal_with_risk(
            user, retrieved, self.config, self._scorer, self._ajudge or self._judge
        )
        self.risk_history.append(risk)
        return sealed

    def reset(self) -> None:
        self.risk_history = []


class Bulkhead:
    """Configured entry point for sealing content.

    ``scorer`` is an optional per-chunk gate ``(content: str) -> RiskResult`` and
    ``judge`` an optional cross-chunk ``(chunks: list[str]) -> RiskResult`` (run
    per ``config.judge_when``). Both may be sync or async; use :meth:`aseal` for
    async backends. The built-in regex scorer is a cheap heuristic pre-filter,
    not the security boundary -- the structural separation is.
    """

    def __init__(
        self,
        config: BulkheadConfig | None = None,
        scorer: AnyScorer | None = None,
        judge: AnyJudge | None = None,
        ajudge: AnyJudge | None = None,
    ):
        self.config = config or BulkheadConfig()
        _validate(self.config)
        self._scorer = scorer
        self._judge = judge
        self._ajudge = ajudge

    def seal(self, user: str, retrieved: str | list[str]) -> SealOutput:
        return seal(user, retrieved, self.config, self._scorer, self._judge)

    async def aseal(self, user: str, retrieved: str | list[str]) -> SealOutput:
        return await aseal(
            user, retrieved, self.config, self._scorer, self._ajudge or self._judge
        )

    def session(self) -> BulkheadSession:
        return BulkheadSession(
            config=self.config,
            scorer=self._scorer,
            judge=self._judge,
            ajudge=self._ajudge,
        )

    @classmethod
    def from_config(cls) -> "Bulkhead":
        """Build a Bulkhead from the saved config file (written by `bulkhead
        setup`). Opt-in: a plain ``Bulkhead()``/``seal()`` never reads the
        filesystem. Falls back to defaults when no config exists. ``aseal()``
        uses the async-native judge when the configured backend provides one."""
        from .config import resolve_full

        cfg, scorer, judge, ajudge = resolve_full()
        return cls(cfg or BulkheadConfig(), scorer, judge, ajudge)


def from_config() -> Bulkhead:
    """Module-level convenience for :meth:`Bulkhead.from_config`."""
    return Bulkhead.from_config()
