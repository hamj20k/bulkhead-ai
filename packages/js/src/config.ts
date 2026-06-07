/**
 * Config file load/save + resolution into a Bulkhead (node only; uses fs/os).
 *
 * Stored as JSON (same schema as the Python package, just JSON) under
 * $BULKHEAD_CONFIG -> ./.bulkhead.json -> $XDG_CONFIG_HOME/bulkhead/config.json
 * (default ~/.config/...). Resolution is OPT-IN via `fromConfig()`; a plain
 * `seal()` never touches the filesystem.
 *
 * JS supports cloud + Ollama judges. (Local in-process gates/judges, ONNX and
 * llama-cpp, live in the Python package.)
 */

import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join } from 'node:path'
import { Bulkhead } from './bulkhead'
import { BulkheadConfigError } from './errors'
import { cloudJudge } from './scorers/cloud'
import { ollamaJudge } from './scorers/ollama'
import type { BulkheadConfig, JudgeScorer } from './types'

const ENV_PATH = 'BULKHEAD_CONFIG'

export interface RawConfig {
  gate?: { runtime?: string; model?: string }
  judge?: {
    runtime?: string
    model?: string
    provider?: string
    key_env?: string
    base_url?: string
  }
  policy?: {
    policy?: BulkheadConfig['policy']
    judge_when?: BulkheadConfig['judgeWhen']
    judge_min_chunks?: number
    judge_on_error?: BulkheadConfig['judgeOnError']
    judge_timeout?: number
    threshold?: number
  }
}

export function defaultConfigPath(): string {
  const base = process.env.XDG_CONFIG_HOME || join(homedir(), '.config')
  return join(base, 'bulkhead', 'config.json')
}

export function resolvedConfigPath(): string | null {
  const override = process.env[ENV_PATH]
  if (override) return existsSync(override) ? override : null
  const local = join(process.cwd(), '.bulkhead.json')
  if (existsSync(local)) return local
  const def = defaultConfigPath()
  return existsSync(def) ? def : null
}

export function writableConfigPath(): string {
  return process.env[ENV_PATH] || defaultConfigPath()
}

export function loadRaw(): RawConfig | null {
  const path = resolvedConfigPath()
  if (!path) return null
  return JSON.parse(readFileSync(path, 'utf-8')) as RawConfig
}

export function saveRaw(data: RawConfig): string {
  const path = writableConfigPath()
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, JSON.stringify(data, null, 2), 'utf-8')
  return path
}

export function clear(): string | null {
  const path = writableConfigPath()
  if (existsSync(path)) {
    rmSync(path)
    return path
  }
  return null
}

export function configFromRaw(raw: RawConfig): BulkheadConfig {
  const p = raw.policy ?? {}
  return {
    policy: p.policy ?? 'warn',
    scorer: { threshold: p.threshold ?? 0.7 },
    judgeWhen: p.judge_when ?? 'suspicious_or_many',
    judgeMinChunks: p.judge_min_chunks ?? 8,
    judgeOnError: p.judge_on_error ?? 'auto',
    judgeTimeout: p.judge_timeout ?? 10000,
  }
}

function buildJudge(raw: RawConfig): JudgeScorer | undefined {
  const j = raw.judge
  if (!j || !j.runtime || j.runtime === 'none') return undefined
  const timeout = raw.policy?.judge_timeout ?? 10000
  if (j.runtime === 'ollama') {
    if (!j.model) throw new BulkheadConfigError('ollama judge requires a model')
    return ollamaJudge({ model: j.model, baseUrl: j.base_url, timeout })
  }
  if (j.runtime === 'cloud') {
    return cloudJudge({
      provider: (j.provider as any) ?? 'openai',
      model: j.model,
      apiKeyEnv: j.key_env,
      baseUrl: j.base_url,
      timeout,
    })
  }
  throw new BulkheadConfigError(
    `judge runtime '${j.runtime}' is not supported in the JS package (use cloud or ollama)`,
  )
}

/** Build a Bulkhead from the saved config file. Opt-in; falls back to defaults
 * (regex) when no config exists. */
export function fromConfig(): Bulkhead {
  const raw = loadRaw()
  if (!raw) return new Bulkhead()
  return new Bulkhead(configFromRaw(raw), undefined, buildJudge(raw))
}
