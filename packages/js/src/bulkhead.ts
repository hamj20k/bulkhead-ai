import { BulkheadConfigError } from './errors'
import { gate } from './gate'
import { GUARD, generateNonce, renderJsonPayload } from './renderer'
import { score } from './scorer'
import type {
  BulkheadConfig,
  BulkheadSession,
  Message,
  PolicyMode,
  RiskResult,
  Scorer,
  ScorerConfig,
  SealInput,
  SealOutput,
} from './types'

const VALID_POLICIES: PolicyMode[] = ['strict', 'warn', 'permissive']

interface ResolvedConfig {
  policy: PolicyMode
  threshold: number
  checkUnicode: boolean
}

function resolveConfig(config: BulkheadConfig = {}): ResolvedConfig {
  const policy = config.policy ?? 'warn'
  if (!VALID_POLICIES.includes(policy)) {
    throw new BulkheadConfigError(
      `policy must be one of ${VALID_POLICIES.join(', ')}, got '${policy}'`,
    )
  }
  const scorer: ScorerConfig = config.scorer ?? {}
  const threshold = scorer.threshold ?? 0.7
  if (threshold < 0 || threshold > 1) {
    throw new BulkheadConfigError(
      `scorer.threshold must be between 0 and 1, got ${threshold}`,
    )
  }
  return { policy, threshold, checkUnicode: scorer.checkUnicode ?? true }
}

function normalizeSources(retrieved: string | string[]): string[] {
  const arr = Array.isArray(retrieved) ? retrieved : [retrieved]
  return arr.filter((s) => s.trim().length > 0)
}

/** Aggregate per-source results into one: max score, unioned flags. */
function aggregate(results: RiskResult[]): RiskResult {
  if (results.length === 0) {
    return { score: 0, flags: [], confidence: 'low', rawMatches: [] }
  }
  const flags = new Set<string>()
  const rawMatches: string[] = []
  let max = results[0]!
  for (const r of results) {
    if (r.score > max.score) max = r
    for (const f of r.flags) flags.add(f)
    rawMatches.push(...r.rawMatches)
  }
  return {
    score: max.score,
    flags: [...flags],
    confidence: max.confidence,
    rawMatches,
  }
}

export class Bulkhead {
  private readonly config: ResolvedConfig
  private readonly scorer: Scorer

  /**
   * @param scorer Optional custom scorer `(content) => RiskResult` that
   * replaces the built-in regex scorer (e.g. an LLM judge or hosted detector).
   * The built-in regex scorer is a cheap heuristic pre-filter, not the security
   * boundary — the structural separation is.
   */
  constructor(config: BulkheadConfig = {}, scorer?: Scorer) {
    this.config = resolveConfig(config)
    this.scorer =
      scorer ?? ((content) => score(content, { checkUnicode: this.config.checkUnicode }))
  }

  /**
   * Separate the trusted USER instruction from untrusted RETRIEVED content.
   * The returned user message is a JSON payload with trusted_instruction and
   * untrusted_inputs fields. Return shape is identical across policy modes.
   */
  async seal(input: SealInput): Promise<SealOutput> {
    const { sealed } = await this.sealWithRisk(input)
    return sealed
  }

  /** Multi-turn session. Accumulates risk history (track-only). */
  session(): BulkheadSession {
    const riskHistory: RiskResult[] = []
    const self = this
    return {
      riskHistory,
      async seal(input: SealInput): Promise<SealOutput> {
        const { sealed, risk } = await self.sealWithRisk(input)
        riskHistory.push(risk)
        return sealed
      },
      reset(): void {
        riskHistory.length = 0
      },
    }
  }

  /** Score once, gate, wrap. Returns both the output and the aggregate risk. */
  private async sealWithRisk(input: SealInput): Promise<{
    sealed: SealOutput
    risk: RiskResult
  }> {
    const sources = normalizeSources(input.retrieved)

    if (sources.length === 0) {
      const instructionMessage: Message = { role: 'user', content: input.user }
      return {
        sealed: { system: '', messages: [instructionMessage] },
        risk: { score: 0, flags: [], confidence: 'low', rawMatches: [] },
      }
    }

    const perSource = await Promise.all(sources.map((s) => this.scorer(s)))
    const risk = aggregate(perSource)

    // gate on the worst source
    gate(risk, this.config.policy, this.config.threshold)

    // The JSON payload keeps the trusted instruction and untrusted inputs in
    // distinct fields. Retrieved never touches system.
    const payloadMessage: Message = {
      role: 'user',
      content: renderJsonPayload(input.user, generateNonce(), sources, perSource),
    }
    return {
      sealed: { system: GUARD, messages: [payloadMessage] },
      risk,
    }
  }
}

/** Convenience standalone seal using a default-config Bulkhead ('warn'). */
const defaultBulkhead = new Bulkhead()
export function seal(input: SealInput): Promise<SealOutput> {
  return defaultBulkhead.seal(input)
}
