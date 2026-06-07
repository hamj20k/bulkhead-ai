export { Bulkhead, seal } from './bulkhead'
export { score } from './scorer'
export { BulkheadInjectionError, BulkheadConfigError } from './errors'

// Ready-made cross-chunk judges (cloud + Ollama). Pass to `new Bulkhead(config,
// scorer, judge)`. The Python package additionally has local ONNX/llama-cpp
// gates and a `bulkhead setup` CLI.
export { cloudJudge } from './scorers/cloud'
export { ollamaJudge } from './scorers/ollama'
export type { CloudJudgeOptions, CloudProvider } from './scorers/cloud'
export type { OllamaJudgeOptions } from './scorers/ollama'
export type {
  TrustLevel,
  PolicyMode,
  Confidence,
  Scorer,
  JudgeScorer,
  JudgeWhen,
  JudgeOnError,
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
