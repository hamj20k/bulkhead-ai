from __future__ import annotations

import warnings

import pytest

from bulkhead.errors import BulkheadInjectionError
from bulkhead.gate import enforce
from bulkhead.types import BulkheadConfig, RiskResult, ScorerConfig

HIGH = RiskResult(score=0.9, flags=["injection_pattern"], confidence="high", raw_matches=["x"])
LOW = RiskResult(score=0.1, flags=[], confidence="low", raw_matches=[])


def _cfg(policy):
    return BulkheadConfig(policy=policy, scorer=ScorerConfig(threshold=0.7))


def test_below_threshold_never_raises_or_warns():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        enforce(LOW, _cfg("strict"))  # no raise despite strict


def test_strict_raises_at_threshold():
    with pytest.raises(BulkheadInjectionError) as exc:
        enforce(HIGH, _cfg("strict"))
    assert "bulkhead" in str(exc.value).lower()


def test_warn_emits_userwarning_but_does_not_raise():
    with pytest.warns(UserWarning, match="bulkhead"):
        enforce(HIGH, _cfg("warn"))


def test_permissive_never_raises_or_warns():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        enforce(HIGH, _cfg("permissive"))
