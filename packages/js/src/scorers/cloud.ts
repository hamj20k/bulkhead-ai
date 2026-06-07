import { BulkheadConfigError } from '../errors'
import type { JudgeScorer } from '../types'
import { JUDGE_PROMPT, httpFetch, joinChunks, parseJudgeJson, timeoutSignal } from './base'

export type CloudProvider = 'openai' | 'groq' | 'anthropic' | 'compatible'

export interface CloudJudgeOptions {
  provider?: CloudProvider
  model?: string
  /** API key, or set apiKeyEnv to read from process.env. */
  apiKey?: string
  apiKeyEnv?: string
  baseUrl?: string
  /** ms; default 10000. */
  timeout?: number
}

const DEFAULT_MODEL: Record<CloudProvider, string> = {
  openai: 'gpt-4o-mini',
  groq: 'llama-3.1-8b-instant',
  compatible: 'gpt-4o-mini',
  anthropic: 'claude-haiku-4-5-20251001',
}
const DEFAULT_BASE_URL: Record<CloudProvider, string> = {
  openai: 'https://api.openai.com/v1',
  groq: 'https://api.groq.com/openai/v1',
  compatible: 'https://api.openai.com/v1',
  anthropic: 'https://api.anthropic.com/v1',
}

function resolveKey(opts: CloudJudgeOptions): string {
  if (opts.apiKey) return opts.apiKey
  if (opts.apiKeyEnv) {
    const k = (globalThis as any).process?.env?.[opts.apiKeyEnv]
    if (k) return k
    throw new BulkheadConfigError(`env var ${opts.apiKeyEnv} is not set (cloud judge key)`)
  }
  throw new BulkheadConfigError('cloud judge requires apiKey or apiKeyEnv')
}

/**
 * Cloud (hosted API) cross-chunk judge: OpenAI / Groq / OpenAI-compatible /
 * Anthropic. Async. PRIVACY: sends retrieved content to the chosen provider.
 */
export function cloudJudge(opts: CloudJudgeOptions = {}): JudgeScorer {
  if (!httpFetch) throw new BulkheadConfigError('global fetch is unavailable (need Node 18+)')
  const provider = opts.provider ?? 'openai'
  const model = opts.model ?? DEFAULT_MODEL[provider]
  const baseUrl = opts.baseUrl ?? DEFAULT_BASE_URL[provider]
  const key = resolveKey(opts)
  const timeout = opts.timeout ?? 10000

  return async (chunks: string[]) => {
    const user = joinChunks(chunks)
    let text: string
    if (provider === 'anthropic') {
      const res = await httpFetch(`${baseUrl}/messages`, {
        method: 'POST',
        signal: timeoutSignal(timeout),
        headers: {
          'content-type': 'application/json',
          'x-api-key': key,
          'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify({
          model,
          system: JUDGE_PROMPT,
          max_tokens: 256,
          messages: [{ role: 'user', content: user }],
        }),
      })
      const data = await res.json()
      text = (data.content ?? []).map((b: any) => b.text ?? '').join('')
    } else {
      const res = await httpFetch(`${baseUrl}/chat/completions`, {
        method: 'POST',
        signal: timeoutSignal(timeout),
        headers: { 'content-type': 'application/json', authorization: `Bearer ${key}` },
        body: JSON.stringify({
          model,
          temperature: 0,
          messages: [
            { role: 'system', content: JUDGE_PROMPT },
            { role: 'user', content: user },
          ],
        }),
      })
      const data = await res.json()
      text = data.choices?.[0]?.message?.content ?? ''
    }
    return parseJudgeJson(text)
  }
}
