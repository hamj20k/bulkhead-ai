import { BulkheadInjectionError } from './errors'
import type { PolicyMode, RiskResult } from './types'

/**
 * Apply the configured policy. Deterministic.
 *
 * - `strict`: throw {@link BulkheadInjectionError} at/above threshold.
 * - `warn`: `console.warn` at/above threshold, then proceed.
 * - `permissive`: never blocks (annotation only).
 *
 * Policy affects whether this throws — never the seal() return shape.
 */
export function gate(
  result: RiskResult,
  policy: PolicyMode,
  threshold: number,
): void {
  if (result.score < threshold) return

  if (policy === 'strict') {
    throw new BulkheadInjectionError(result)
  }

  if (policy === 'warn') {
    console.warn(
      `[bulkhead] High injection risk detected. ` +
        `score=${result.score.toFixed(2)} flags=[${result.flags.join(',')}]. ` +
        `Proceeding because policy is 'warn'.`,
    )
  }
  // permissive — do nothing, annotation only
}
