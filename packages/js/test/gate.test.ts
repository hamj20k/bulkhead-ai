import { afterEach, describe, expect, it, vi } from 'vitest'
import { gate } from '../src/gate'
import { BulkheadInjectionError } from '../src/errors'
import type { RiskResult } from '../src/types'

const HIGH: RiskResult = {
  score: 0.9,
  flags: ['injection_pattern'],
  confidence: 'high',
  rawMatches: ['x'],
}
const LOW: RiskResult = { score: 0.1, flags: [], confidence: 'low', rawMatches: [] }

describe('gate', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('does nothing below threshold even in strict mode', () => {
    expect(() => gate(LOW, 'strict', 0.7)).not.toThrow()
  })

  it('throws in strict mode at/above threshold', () => {
    expect(() => gate(HIGH, 'strict', 0.7)).toThrow(BulkheadInjectionError)
    try {
      gate(HIGH, 'strict', 0.7)
    } catch (e) {
      expect((e as Error).message.toLowerCase()).toContain('bulkhead')
    }
  })

  it('warns but does not throw in warn mode', () => {
    const spy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(() => gate(HIGH, 'warn', 0.7)).not.toThrow()
    expect(spy).toHaveBeenCalledOnce()
    expect(spy.mock.calls[0]![0]).toContain('bulkhead')
  })

  it('never throws or warns in permissive mode', () => {
    const spy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(() => gate(HIGH, 'permissive', 0.7)).not.toThrow()
    expect(spy).not.toHaveBeenCalled()
  })
})
