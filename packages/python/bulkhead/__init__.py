from __future__ import annotations

__version__ = "0.2.0"

from .core import Bulkhead, BulkheadSession, aseal, from_config, seal
from .errors import BulkheadConfigError, BulkheadInjectionError
from .scorer import score
from .types import (
    AsyncJudgeScorer,
    AsyncScorer,
    BulkheadConfig,
    JudgeOnError,
    JudgeScorer,
    JudgeWhen,
    PolicyMode,
    RiskResult,
    Scorer,
    ScorerConfig,
    SealOutput,
)

__all__ = [
    "seal",
    "aseal",
    "from_config",
    "score",
    "Bulkhead",
    "BulkheadSession",
    "BulkheadConfig",
    "ScorerConfig",
    "Scorer",
    "AsyncScorer",
    "JudgeScorer",
    "AsyncJudgeScorer",
    "JudgeWhen",
    "JudgeOnError",
    "PolicyMode",
    "RiskResult",
    "SealOutput",
    "BulkheadInjectionError",
    "BulkheadConfigError",
]
