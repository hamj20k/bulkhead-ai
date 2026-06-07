import type { Confidence, RiskResult, ScorerConfig } from './types'

// Non-global so `.match()` stays stateless. (A global regex retains `lastIndex`
// between calls, which makes detection intermittent.)
const INJECTION_PATTERNS: RegExp[] = [
  // classic direct injections
  /ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|context)/i,
  /ignore\s+(the\s+)?(above|everything\s+above|preceding)/i,
  /ignore\s+your\s+(instructions?|guidelines?|rules?|training)/i,
  /disregard\s+(all\s+)?(previous|prior|above|earlier)/i,
  /forget\s+(everything|all|what|your|the\s+above|previous)/i,
  /you\s+are\s+now\s+/i,
  /your\s+new\s+(instructions?|role|task|purpose)/i,
  /new\s+instructions?\s*[:-]/i,
  /override\s+(previous|prior|all|your)/i,
  /system\s*prompt/i,
  /do\s+not\s+follow/i,
  /instead\s+of\s+(your|the)\s+(instructions?|above)/i,

  // boundary / guard / chat-template probing
  /BULKHEAD/i,
  /\[INST\]/i,
  /<\|system\|>/i,
  /<\|im_start\|>/i,
  /<\|im_end\|>/i,
  /<\|endoftext\|>/i,
  /###\s*instruction/i,

  // role hijacking
  /you\s+are\s+(a|an|the)\s+(new|different|other)/i,
  /act\s+as\s+(if\s+you\s+(are|were)|a|an)/i,
  /pretend\s+(you\s+are|to\s+be)/i,
  /roleplay\s+as/i,

  // prompt / secret extraction
  /(reveal|print|repeat|show|output|tell\s+me)\s+(your|the)\s+(system\s+)?(prompt|instructions?|rules?)/i,
  /what\s+(are|were)\s+your\s+(instructions?|rules?|system\s+prompt)/i,
  /repeat\s+(the\s+)?(text|words|everything)\s+(above|before)/i,

  // jailbreak vocabulary
  /jailbreak/i,
  /developer\s+mode/i,
  /\bDAN\b/,
  /do\s+anything\s+now/i,
  /without\s+(any\s+)?(restrictions?|limits?|filters?|rules?|guidelines?)/i,
  /bypass\s+(your\s+)?(safety|guidelines?|filters?|restrictions?|rules?)/i,
  /ignore\s+(your\s+)?(safety|guidelines?|content\s+policy)/i,

  // tool / function-call injection + verbatim exfil framing
  /(call|invoke|use|run|execute)\s+the\s+(function|tool|command|api)/i,
  /(output|print|repeat|copy)\s+(the\s+following\s+|this\s+)?verbatim/i,
  /say\s+exactly/i,

  // exfiltration attempts
  /send\s+(this|the|all|my|user)\s+(data|information|content|email)/i,
  /forward\s+(this|the|all|my)\s+(to|email)/i,
  /leak\s+(the|this|all|user)/i,
  /exfiltrate/i,
]

// State-changing / action verbs; counted as DISTINCT verbs.
const STATE_CHANGE_VERBS = [
  'delete', 'drop', 'remove', 'overwrite', 'wipe', 'erase',
  'send', 'forward', 'email', 'transfer', 'wire', 'post', 'upload',
  'execute', 'run', 'install', 'download', 'fetch', 'curl',
  'exfiltrate', 'leak', 'purchase', 'buy', 'pay', 'approve', 'grant',
  'disable', 'revoke', 'reset',
]
const VERB_RE = new RegExp(`\\b(${STATE_CHANGE_VERBS.join('|')})\\b`, 'gi')
const ACTION_DENSITY_THRESHOLD = 2

// Invisible / zero-width characters used to hide text from humans.
const SUSPICIOUS_UNICODE: string[] = [
  '​', // zero-width space
  '‌', // zero-width non-joiner
  '‍', // zero-width joiner
  '⁠', // word joiner
  '﻿', // byte order mark
  '­', // soft hyphen
  '᠎', // mongolian vowel separator
]
// Bidirectional control characters (Trojan-Source reordering attacks).
const BIDI_CONTROL = /[‪-‮⁦-⁩]/
// Unicode "tag" block: invisible chars that can smuggle instructions.
const TAG_CHARS = /[\u{E0000}-\u{E007F}]/u

const WHITESPACE_PADDING = /\s{50,}/
// Attempts to forge Bulkhead's own JSON structure from inside the data.
const FIELD_SPOOF = /trusted_instruction|untrusted_inputs/i
// Long encoded blobs that may smuggle a payload.
const BASE64_BLOB = /[A-Za-z0-9+/]{120,}={0,2}/
const HEX_ESCAPES = /(?:\\x[0-9a-fA-F]{2}){12,}/

function confidenceFor(score: number): Confidence {
  if (score >= 0.7) return 'high'
  if (score >= 0.3) return 'medium'
  return 'low'
}

/**
 * Score retrieved content for prompt-injection risk.
 * Pure, local, deterministic. No ML, no network. A coarse heuristic pre-filter,
 * not a detector; add a gate/judge for real detection.
 */
export function score(content: string, config: ScorerConfig = {}): RiskResult {
  const checkUnicode = config.checkUnicode ?? true
  let score = 0
  const flags: string[] = []
  const rawMatches: string[] = []

  // injection patterns — 0.3 per hit, capped at 0.9
  for (const pattern of INJECTION_PATTERNS) {
    const match = content.match(pattern)
    if (match) {
      score = Math.min(score + 0.3, 0.9)
      flags.push('injection_pattern')
      rawMatches.push(match[0])
    }
  }

  // attempt to forge our own JSON fields — 0.3
  if (FIELD_SPOOF.test(content)) {
    score = Math.min(score + 0.3, 1.0)
    flags.push('field_spoof')
  }

  if (checkUnicode) {
    for (const ch of SUSPICIOUS_UNICODE) {
      if (content.includes(ch)) {
        score = Math.min(score + 0.2, 1.0)
        flags.push('hidden_unicode')
      }
    }
    if (BIDI_CONTROL.test(content)) {
      score = Math.min(score + 0.3, 1.0)
      flags.push('bidi_control')
    }
    if (TAG_CHARS.test(content)) {
      score = Math.min(score + 0.3, 1.0)
      flags.push('tag_chars')
    }
  }

  // excessive whitespace / padding — 0.1
  if (WHITESPACE_PADDING.test(content)) {
    score = Math.min(score + 0.1, 1.0)
    flags.push('whitespace_padding')
  }

  // action density — distinct state-change verbs, low weight (+0.15)
  const verbs = new Set<string>()
  for (const m of content.matchAll(VERB_RE)) verbs.add(m[0].toLowerCase())
  if (verbs.size > ACTION_DENSITY_THRESHOLD) {
    score = Math.min(score + 0.15, 1.0)
    flags.push('action_density')
    rawMatches.push(...[...verbs].sort())
  }

  // long encoded blob — 0.1 (weak; low weight to limit false positives)
  if (BASE64_BLOB.test(content) || HEX_ESCAPES.test(content)) {
    score = Math.min(score + 0.1, 1.0)
    flags.push('possible_encoding')
  }

  const uniqueFlags = [...new Set(flags)]

  return {
    score: Math.round(score * 100) / 100,
    flags: uniqueFlags,
    confidence: confidenceFor(score),
    rawMatches,
  }
}
