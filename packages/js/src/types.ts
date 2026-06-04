export type TrustLevel = 'user' | 'retrieved'

export type PolicyMode = 'strict' | 'warn' | 'permissive'

export type Confidence = 'low' | 'medium' | 'high'

export interface ScorerConfig {
  /** Block/warn threshold. Default: 0.7 */
  threshold?: number
  /** Detect zero-width / hidden unicode. Default: true */
  checkUnicode?: boolean
}

export interface BulkheadConfig {
  /** Default: 'warn' */
  policy?: PolicyMode
  scorer?: ScorerConfig
}

export interface RiskResult {
  score: number
  flags: string[]
  confidence: Confidence
  rawMatches: string[]
}

/**
 * A scorer maps content to a {@link RiskResult}. Swap the built-in regex
 * scorer for your own (e.g. an LLM judge or hosted detector). May be sync or
 * async — `seal()` awaits it.
 */
export type Scorer = (content: string) => RiskResult | Promise<RiskResult>

export interface SealInput {
  user: string
  /** Untrusted external content. Array accepted for multiple sources. */
  retrieved: string | string[]
}

export type MessageRole = 'system' | 'user'

export interface Message {
  role: MessageRole
  content: string
}

/**
 * The result of `seal()`. Spreads directly into the Vercel AI SDK:
 * `generateText({ model, ...sealed })` → `{ model, system, messages }`.
 *
 * Invariant: untrusted retrieved content lives in `untrusted_inputs` inside a
 * JSON `user` message (data position), never `system`. `system` holds only the
 * trusted guard preamble.
 */
export interface SealOutput {
  /** Trusted system guard ('' when nothing was retrieved). */
  system: string
  /** JSON payload message, or the plain instruction when no retrieved data exists. */
  messages: Message[]
}

export interface BulkheadSession {
  seal: (input: SealInput) => Promise<SealOutput>
  riskHistory: RiskResult[]
  reset: () => void
}
