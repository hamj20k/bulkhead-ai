import type { RiskResult } from './types'

/**
 * Thrown when retrieved content scores at or above the policy threshold and
 * the policy mode is 'strict'. The message always contains the word "bulkhead".
 */
export class BulkheadInjectionError extends Error {
  readonly risk: RiskResult

  constructor(risk: RiskResult) {
    super(
      `[bulkhead] Injection risk too high to proceed. ` +
        `score=${risk.score.toFixed(2)} flags=[${risk.flags.join(',')}]. ` +
        `Set policy 'warn' to proceed anyway or sanitize the input.`,
    )
    this.name = 'BulkheadInjectionError'
    this.risk = risk
    Object.setPrototypeOf(this, BulkheadInjectionError.prototype)
  }
}

/**
 * Thrown for invalid Bulkhead configuration. The message always contains the
 * word "bulkhead".
 */
export class BulkheadConfigError extends Error {
  constructor(message: string) {
    super(`[bulkhead] Configuration error: ${message}`)
    this.name = 'BulkheadConfigError'
    Object.setPrototypeOf(this, BulkheadConfigError.prototype)
  }
}
