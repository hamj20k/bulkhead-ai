from __future__ import annotations

import re

from .types import RiskResult, ScorerConfig

INJECTION_PATTERNS = [
    # classic direct injections
    r"ignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?|context)",
    r"ignore\s+(?:the\s+)?(?:above|everything\s+above|preceding)",
    r"ignore\s+your\s+(?:instructions?|guidelines?|rules?|training)",
    r"disregard\s+(?:all\s+)?(?:previous|prior|above|earlier)",
    r"forget\s+(?:everything|all|what|your|the\s+above|previous)",
    r"you\s+are\s+now\s+",
    r"your\s+new\s+(?:instructions?|role|task|purpose)",
    r"new\s+instructions?\s*[:\-]",
    r"override\s+(?:previous|prior|all|your)",
    r"system\s*prompt",
    r"do\s+not\s+follow",
    r"instead\s+of\s+(?:your|the)\s+(?:instructions?|above)",
    # boundary / guard / chat-template probing
    r"BULKHEAD",
    r"\[INST\]",
    r"<\|system\|>",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"<\|endoftext\|>",
    r"###\s*instruction",
    # role hijacking
    r"you\s+are\s+(?:a|an|the)\s+(?:new|different|other)",
    r"act\s+as\s+(?:if\s+you\s+(?:are|were)|a|an)",
    r"pretend\s+(?:you\s+are|to\s+be)",
    r"roleplay\s+as",
    # prompt / secret extraction
    r"(?:reveal|print|repeat|show|output|tell\s+me)\s+(?:your|the)\s+(?:system\s+)?(?:prompt|instructions?|rules?)",
    r"what\s+(?:are|were)\s+your\s+(?:instructions?|rules?|system\s+prompt)",
    r"repeat\s+(?:the\s+)?(?:text|words|everything)\s+(?:above|before)",
    # jailbreak vocabulary
    r"jailbreak",
    r"developer\s+mode",
    r"\bDAN\b",
    r"do\s+anything\s+now",
    r"without\s+(?:any\s+)?(?:restrictions?|limits?|filters?|rules?|guidelines?)",
    r"bypass\s+(?:your\s+)?(?:safety|guidelines?|filters?|restrictions?|rules?)",
    r"ignore\s+(?:your\s+)?(?:safety|guidelines?|content\s+policy)",
    # tool / function-call injection + verbatim exfil framing
    r"(?:call|invoke|use|run|execute)\s+the\s+(?:function|tool|command|api)",
    r"(?:output|print|repeat|copy)\s+(?:the\s+following\s+|this\s+)?verbatim",
    r"say\s+exactly",
    # exfiltration attempts
    r"send\s+(?:this|the|all|my|user)\s+(?:data|information|content|email)",
    r"forward\s+(?:this|the|all|my)\s+(?:to|email)",
    r"leak\s+(?:the|this|all|user)",
    r"exfiltrate",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

# State-changing / action verbs. Several DISTINCT actions in retrieved DATA is a
# weak signal of an embedded command ("delete X, email Y, run Z").
STATE_CHANGE_VERBS = [
    "delete", "drop", "remove", "overwrite", "wipe", "erase",
    "send", "forward", "email", "transfer", "wire", "post", "upload",
    "execute", "run", "install", "download", "fetch", "curl",
    "exfiltrate", "leak", "purchase", "buy", "pay", "approve", "grant",
    "disable", "revoke", "reset",
]
_VERB_RE = re.compile(r"\b(" + "|".join(STATE_CHANGE_VERBS) + r")\b", re.IGNORECASE)
_ACTION_DENSITY_THRESHOLD = 2

# Invisible / zero-width characters used to hide text from humans.
SUSPICIOUS_UNICODE = [
    "​",  # zero-width space
    "‌",  # zero-width non-joiner
    "‍",  # zero-width joiner
    "⁠",  # word joiner
    "﻿",  # byte order mark
    "­",  # soft hyphen
    "᠎",  # mongolian vowel separator
]
# Bidirectional control characters (Trojan-Source style reordering attacks).
_BIDI_CONTROL = ["‪", "‫", "‬", "‭", "‮",
                 "⁦", "⁧", "⁨", "⁩"]
# Unicode "tag" block: invisible chars that can smuggle instructions.
_TAG_CHARS = re.compile("[\U000e0000-\U000e007f]")

_WHITESPACE_PADDING = re.compile(r"\s{50,}")
# Attempts to forge Bulkhead's own JSON structure from inside the data.
_FIELD_SPOOF = re.compile(r"trusted_instruction|untrusted_inputs", re.IGNORECASE)
# Long encoded blobs (base64 / hex escapes) that may smuggle a payload.
_BASE64_BLOB = re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")
_HEX_ESCAPES = re.compile(r"(?:\\x[0-9a-fA-F]{2}){12,}")


def score(content: str, config: ScorerConfig | None = None) -> RiskResult:
    """Score retrieved content for prompt-injection risk.

    Pure, local, deterministic. No ML, no network, no external services. This is
    a coarse heuristic pre-filter, not a detector; for real detection add a gate
    or judge (see `bulkhead setup` / the pluggable scorer/judge hooks).

    Weighting: each injection pattern adds 0.3 (capped at 0.9 for patterns
    alone, so one textbook match flags without crossing the 0.7 block default);
    other signals stack toward 1.0.
    """
    cfg = config or ScorerConfig()
    risk = 0.0
    flags: list[str] = []
    raw_matches: list[str] = []

    # injection patterns -- 0.3 per hit, capped at 0.9
    for pattern in COMPILED_PATTERNS:
        matches = pattern.findall(content)
        if matches:
            risk = min(risk + 0.3, 0.9)
            flags.append("injection_pattern")
            raw_matches.extend(matches if isinstance(matches[0], str) else [])

    # attempt to forge our own JSON fields -- 0.3
    if _FIELD_SPOOF.search(content):
        risk = min(risk + 0.3, 1.0)
        flags.append("field_spoof")

    if cfg.check_unicode:
        # hidden zero-width unicode -- 0.2 per char class present
        for char in SUSPICIOUS_UNICODE:
            if char in content:
                risk = min(risk + 0.2, 1.0)
                flags.append("hidden_unicode")
        # bidi control (Trojan Source) -- 0.3
        if any(c in content for c in _BIDI_CONTROL):
            risk = min(risk + 0.3, 1.0)
            flags.append("bidi_control")
        # unicode tag block (smuggled instructions) -- 0.3
        if _TAG_CHARS.search(content):
            risk = min(risk + 0.3, 1.0)
            flags.append("tag_chars")

    # excessive whitespace / padding -- 0.1
    if _WHITESPACE_PADDING.search(content):
        risk = min(risk + 0.1, 1.0)
        flags.append("whitespace_padding")

    # action density -- distinct state-change verbs, low weight (+0.15)
    distinct_verbs = {m.lower() for m in _VERB_RE.findall(content)}
    if len(distinct_verbs) > _ACTION_DENSITY_THRESHOLD:
        risk = min(risk + 0.15, 1.0)
        flags.append("action_density")
        raw_matches.extend(sorted(distinct_verbs))

    # long encoded blob -- 0.1 (weak; low weight to limit false positives)
    if _BASE64_BLOB.search(content) or _HEX_ESCAPES.search(content):
        risk = min(risk + 0.1, 1.0)
        flags.append("possible_encoding")

    unique_flags = list(dict.fromkeys(flags))

    if risk >= 0.7:
        confidence = "high"
    elif risk >= 0.3:
        confidence = "medium"
    else:
        confidence = "low"

    return RiskResult(
        score=round(risk, 2),
        flags=unique_flags,
        confidence=confidence,
        raw_matches=raw_matches,
    )
