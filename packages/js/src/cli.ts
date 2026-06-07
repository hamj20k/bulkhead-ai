/**
 * `bulkhead` CLI (JS). Configures the cloud/Ollama judge; use `fromConfig()`.
 *   bulkhead setup --recommended     Ollama judge (local)
 *   bulkhead setup --judge ollama:llama3.2:3b
 *   bulkhead setup --judge cloud:groq --key-env GROQ_API_KEY
 *   bulkhead setup --reset
 *   bulkhead status
 *
 * The JS package supports cloud + Ollama judges. Local in-process gates (ONNX,
 * llama-cpp) live in the Python package.
 */

import * as cfg from './config'
import type { RawConfig } from './config'

function parseSlot(value: string): { runtime: string; model?: string; provider?: string } {
  const [runtime, ...rest] = value.split(':')
  const tail = rest.join(':')
  if (runtime === 'cloud') return { runtime, provider: tail || 'openai' }
  return tail ? { runtime: runtime!, model: tail } : { runtime: runtime! }
}

function getFlag(argv: string[], name: string): string | undefined {
  const i = argv.indexOf(name)
  return i >= 0 ? argv[i + 1] : undefined
}

function cmdStatus(): number {
  const path = cfg.resolvedConfigPath()
  if (!path) {
    console.log('No Bulkhead config. Using the regex default. Run `bulkhead setup`.')
    return 0
  }
  const raw = cfg.loadRaw() ?? {}
  const judge = raw.judge ?? { runtime: 'none' }
  console.log(`Config: ${path}`)
  console.log(`  judge: ${judge.runtime ?? 'none'} ${judge.model ?? judge.provider ?? ''}`.trimEnd())
  console.log(`  judge_when: ${raw.policy?.judge_when ?? 'suspicious_or_many'}`)
  if (judge.runtime === 'cloud' && judge.key_env) {
    console.log(`  cloud key ${judge.key_env}: ${process.env[judge.key_env] ? 'set' : 'MISSING'}`)
  }
  return 0
}

function cmdSetup(argv: string[]): number {
  if (argv.includes('--reset')) {
    const removed = cfg.clear()
    console.log(removed ? `Removed ${removed}.` : 'No config to remove.')
    return 0
  }

  const judgeWhen = getFlag(argv, '--judge-when') ?? 'suspicious_or_many'
  let raw: RawConfig

  if (argv.includes('--recommended')) {
    raw = {
      judge: { runtime: 'ollama', model: 'llama3.2:3b' },
      policy: { policy: 'warn', judge_when: judgeWhen as any },
    }
  } else {
    const judgeArg = getFlag(argv, '--judge')
    if (!judgeArg) {
      console.log('Usage: bulkhead setup --recommended | --judge <ollama:model|cloud:provider> [--key-env VAR]')
      return 1
    }
    const slot = parseSlot(judgeArg)
    const judge: RawConfig['judge'] = { runtime: slot.runtime }
    if (slot.model) judge.model = slot.model
    if (slot.runtime === 'cloud') {
      judge.provider = slot.provider
      judge.key_env = getFlag(argv, '--key-env') ?? 'OPENAI_API_KEY'
      console.log(`PRIVACY: a cloud judge sends retrieved content to ${slot.provider}.`)
    }
    raw = { judge, policy: { judge_when: judgeWhen as any } }
  }

  const path = cfg.saveRaw(raw)
  console.log(`Wrote config to ${path}`)
  if (raw.judge?.runtime === 'ollama') {
    console.log(`Judge: Ollama '${raw.judge.model}'. Pull it with: ollama pull ${raw.judge.model}`)
  }
  if (raw.judge?.runtime === 'cloud') {
    console.log(`Judge: cloud '${raw.judge.provider}'. Set ${raw.judge.key_env} in your environment.`)
  }
  console.log('Done. In code: import { fromConfig } from "bulkhead-ai/config"; const bh = fromConfig()')
  return 0
}

export function main(argv: string[] = process.argv.slice(2)): number {
  const [command, ...rest] = argv
  if (command === 'status') return cmdStatus()
  if (command === 'setup') return cmdSetup(rest)
  console.log('bulkhead <setup|status>  (try `bulkhead setup --recommended`)')
  return 0
}
