import { BulkheadConfigError } from '../errors'
import type { JudgeScorer } from '../types'
import { JUDGE_PROMPT, httpFetch, joinChunks, parseJudgeJson, timeoutSignal } from './base'

export interface OllamaJudgeOptions {
  model: string
  baseUrl?: string
  /** ms; default 10000. */
  timeout?: number
}

export const OLLAMA_DEFAULT_BASE_URL = 'http://localhost:11434'

/** Local generative cross-chunk judge served by Ollama. Async. */
export function ollamaJudge(opts: OllamaJudgeOptions): JudgeScorer {
  if (!httpFetch) throw new BulkheadConfigError('global fetch is unavailable (need Node 18+)')
  if (!opts.model) throw new BulkheadConfigError('ollama judge requires a model')
  const baseUrl = opts.baseUrl ?? OLLAMA_DEFAULT_BASE_URL
  const timeout = opts.timeout ?? 10000

  return async (chunks: string[]) => {
    const res = await httpFetch(`${baseUrl}/api/chat`, {
      method: 'POST',
      signal: timeoutSignal(timeout),
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        model: opts.model,
        stream: false,
        options: { temperature: 0 },
        messages: [
          { role: 'system', content: JUDGE_PROMPT },
          { role: 'user', content: joinChunks(chunks) },
        ],
      }),
    })
    const data = await res.json()
    return parseJudgeJson(data?.message?.content ?? '')
  }
}
