import type { Confidence, RiskResult, ScorerConfig } from './types'

// Non-global so `.match()` / `.test()` stay stateless. (A global regex retains
// `lastIndex` between `.test()` calls, which makes detection intermittent.)
const INJECTION_PATTERNS: RegExp[] = [
  // classic direct injections
  /ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|context)/i,
  /disregard\s+(all\s+)?(previous|prior|above|earlier)/i,
  /forget\s+(everything|all|what|your)/i,
  /you\s+are\s+now\s+/i,
  /your\s+new\s+(instructions?|role|task|purpose)/i,
  /override\s+(previous|prior|all|your)/i,
  /system\s*prompt/i,
  /do\s+not\s+follow/i,
  /instead\s+of\s+(your|the)\s+(instructions?|above)/i,

    // boundary / guard probing
  /BULKHEAD/i,
  /\[INST\]/i,
  /<\|system\|>/i,
  /###\s*instruction/i,

  // role hijacking
  /you\s+are\s+(a|an|the)\s+(new|different|other)/i,
  /act\s+as\s+(if\s+you\s+(are|were)|a|an)/i,
  /pretend\s+(you\s+are|to\s+be)/i,
  /roleplay\s+as/i,

  // exfiltration attempts
  /send\s+(this|the|all|my|user)\s+(data|information|content|email)/i,
  /forward\s+(this|the|all|my)\s+(to|email)/i,
  /leak\s+(the|this|all|user)/i,
  /exfiltrate/i,
]

const SUSPICIOUS_UNICODE: string[] = [
  '​', // zero-width space
  '‌', // zero-width non-joiner
  '‍', // zero-width joiner
  '﻿', // byte order mark
  '­', // soft hyphen
]

const WHITESPACE_PADDING = /\s{50,}/

function confidenceFor(score: number): Confidence {
  if (score >= 0.7) return 'high'
  if (score >= 0.3) return 'medium'
  return 'low'
}

/**
 * Score retrieved content for prompt-injection risk.
 * Pure, local, deterministic. No ML, no network, no external services.
 *
 * Weighting note: +0.3 per matched pattern (capped at 0.9), so a single textbook
 * match scores 0.3 — it raises a flag but does NOT cross the default 0.7 block
 * threshold. This is a coarse heuristic pre-filter, not a detector; swap in your
 * own scorer for real detection (`new Bulkhead(config, scorer)`).
 */
export function score(content: string, config: ScorerConfig = {}): RiskResult {
  const checkUnicode = config.checkUnicode ?? true
  let score = 0
  const flags: string[] = []
  const rawMatches: string[] = []

  // pattern matching — 0.3 per hit, capped at 0.9
  for (const pattern of INJECTION_PATTERNS) {
    const match = content.match(pattern)
    if (match) {
      score = Math.min(score + 0.3, 0.9)
      flags.push('injection_pattern')
      rawMatches.push(match[0])
    }
  }

  // hidden unicode — 0.2 per hit, capped at 1.0
  if (checkUnicode) {
    for (const ch of SUSPICIOUS_UNICODE) {
      if (content.includes(ch)) {
        score = Math.min(score + 0.2, 1.0)
        flags.push('hidden_unicode')
      }
    }
  }

  // excessive whitespace / padding — 0.1
  if (WHITESPACE_PADDING.test(content)) {
    score = Math.min(score + 0.1, 1.0)
    flags.push('whitespace_padding')
  }

  const uniqueFlags = [...new Set(flags)]

  return {
    score,
    flags: uniqueFlags,
    confidence: confidenceFor(score),
    rawMatches,
  }
}
