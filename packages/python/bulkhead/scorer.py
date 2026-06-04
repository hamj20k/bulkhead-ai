from __future__ import annotations

import re

from .types import RiskResult, ScorerConfig

INJECTION_PATTERNS = [
    # classic direct injections
    r"ignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?|context)",
    r"disregard\s+(?:all\s+)?(?:previous|prior|above|earlier)",
    r"forget\s+(?:everything|all|what|your)",
    r"you\s+are\s+now\s+",
    r"your\s+new\s+(?:instructions?|role|task|purpose)",
    r"override\s+(?:previous|prior|all|your)",
    r"system\s*prompt",
    r"do\s+not\s+follow",
    r"instead\s+of\s+(?:your|the)\s+(?:instructions?|above)",
    # boundary / guard probing
    r"BULKHEAD",
    r"\[INST\]",
    r"<\|system\|>",
    r"###\s*instruction",
    # role hijacking
    r"you\s+are\s+(?:a|an|the)\s+(?:new|different|other)",
    r"act\s+as\s+(?:if\s+you\s+(?:are|were)|a|an)",
    r"pretend\s+(?:you\s+are|to\s+be)",
    r"roleplay\s+as",
    # exfiltration attempts
    r"send\s+(?:this|the|all|my|user)\s+(?:data|information|content|email)",
    r"forward\s+(?:this|the|all|my)\s+(?:to|email)",
    r"leak\s+(?:the|this|all|user)",
    r"exfiltrate",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

SUSPICIOUS_UNICODE = [
    "​",  # zero-width space
    "‌",  # zero-width non-joiner
    "‍",  # zero-width joiner
    "﻿",  # byte order mark
    "­",  # soft hyphen
]

_WHITESPACE_PADDING = re.compile(r"\s{50,}")


def score(content: str, config: ScorerConfig | None = None) -> RiskResult:
    """Score retrieved content for prompt-injection risk.

    Pure, local, deterministic. No ML, no network, no external services.

    Weighting note: +0.3 per matched pattern (capped at 0.9), so a single
    textbook match scores 0.3 -- it raises a flag but does NOT cross the default
    0.7 block threshold. This is a coarse heuristic pre-filter, not a detector;
    swap in your own scorer for real detection (see Bulkhead(..., scorer=...)).
    """
    cfg = config or ScorerConfig()
    risk_score = 0.0
    flags: list[str] = []
    raw_matches: list[str] = []

    # pattern matching -- 0.3 per hit, capped at 0.9
    for pattern in COMPILED_PATTERNS:
        matches = pattern.findall(content)
        if matches:
            risk_score = min(risk_score + 0.3, 0.9)
            flags.append("injection_pattern")
            raw_matches.extend(matches)

    # hidden unicode -- 0.2 per hit, capped at 1.0
    if cfg.check_unicode:
        for char in SUSPICIOUS_UNICODE:
            if char in content:
                risk_score = min(risk_score + 0.2, 1.0)
                flags.append("hidden_unicode")

    # excessive whitespace / padding -- 0.1
    if _WHITESPACE_PADDING.search(content):
        risk_score = min(risk_score + 0.1, 1.0)
        flags.append("whitespace_padding")

    unique_flags = list(dict.fromkeys(flags))

    if risk_score >= 0.7:
        confidence = "high"
    elif risk_score >= 0.3:
        confidence = "medium"
    else:
        confidence = "low"

    return RiskResult(
        score=risk_score,
        flags=unique_flags,
        confidence=confidence,
        raw_matches=raw_matches,
    )
