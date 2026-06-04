from __future__ import annotations

import warnings

from .errors import BulkheadInjectionError
from .types import BulkheadConfig, RiskResult


def enforce(risk_result: RiskResult, config: BulkheadConfig) -> None:
    """Apply the configured policy. Deterministic.

    - ``strict``: raise :class:`BulkheadInjectionError` at/above threshold.
    - ``warn``: emit a ``UserWarning`` at/above threshold, then proceed.
    - ``permissive``: never blocks (annotation only).

    Policy affects whether this raises -- never the seal() return shape.
    """
    threshold = config.scorer.threshold

    if risk_result.score < threshold:
        return

    if config.policy == "strict":
        raise BulkheadInjectionError(
            score=risk_result.score,
            flags=risk_result.flags,
        )

    if config.policy == "warn":
        warnings.warn(
            f"[bulkhead] High injection risk detected. "
            f"score={risk_result.score:.2f} "
            f"flags={risk_result.flags}. "
            f"Proceeding because policy='warn'.",
            UserWarning,
            stacklevel=3,
        )
    # permissive -- do nothing, annotation only
