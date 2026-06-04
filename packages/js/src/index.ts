export { Bulkhead, seal } from './bulkhead'
export { score } from './scorer'
export { BulkheadInjectionError, BulkheadConfigError } from './errors'
export type {
  TrustLevel,
  PolicyMode,
  Confidence,
  Scorer,
  ScorerConfig,
  BulkheadConfig,
  RiskResult,
  SealInput,
  SealOutput,
  Message,
  MessageRole,
  BulkheadSession,
} from './types'

// Vercel AI SDK drop-in wrappers. Importing these pulls the `ai` peer
// dependency; install it alongside bulkhead-ai (`npm i bulkhead-ai ai`).
export { generateText, streamText } from '../wrappers/vercel-ai'
