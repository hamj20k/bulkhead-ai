import type { generateText as AiGenerateText, streamText as AiStreamText } from 'ai'
import { Bulkhead } from '../src/bulkhead'
import type { SealInput } from '../src/types'

// `ai` types are erased at build time; the runtime import is lazy (below) so
// that `import { Bulkhead } from 'bulkhead-ai'` works without `ai` installed.
type GenerateTextParams = Parameters<typeof AiGenerateText>[0]
type StreamTextParams = Parameters<typeof AiStreamText>[0]

/** Native params plus the one new field: `retrieved` (the untrusted bucket). */
type WithRetrieved<T> = T & { retrieved?: SealInput['retrieved'] }

const bulkhead = new Bulkhead()

function trustedInstructionFromParams(params: {
  prompt?: unknown
  messages?: unknown
}): string {
  if (typeof params.prompt === 'string') return params.prompt
  if (Array.isArray(params.messages)) {
    return JSON.stringify({ trusted_messages: params.messages }, null, 2)
  }
  return ''
}

async function applySeal<
  T extends { prompt?: unknown; system?: unknown; messages?: unknown },
>(params: WithRetrieved<T>): Promise<T> {
  const { retrieved, ...rest } = params
  if (retrieved === undefined) {
    return rest as unknown as T
  }

  const user = trustedInstructionFromParams(params)
  const sealed = await bulkhead.seal({ user, retrieved })

  // Merge any developer-authored system prompt with the bulkhead guard.
  const existingSystem =
    typeof params.system === 'string' ? params.system : undefined
  const system =
    existingSystem && sealed.system
      ? `${existingSystem}\n\n${sealed.system}`
      : sealed.system || existingSystem || ''

  // The Vercel SDK rejects `prompt` + `messages` together: emit the sealed
  // JSON message and drop the original prompt/messages after copying them into
  // trusted_instruction.
  const {
    prompt: _prompt,
    messages: _messages,
    system: _system,
    ...clean
  } = rest as Record<string, unknown>

  return {
    ...(clean as unknown as T),
    ...(system ? { system } : {}),
    messages: sealed.messages,
  }
}

/**
 * Drop-in replacement for the Vercel AI SDK `generateText`, accepting one extra
 * field: `retrieved`. Untrusted content is sealed before the model call.
 */
export async function generateText(
  params: WithRetrieved<GenerateTextParams>,
): ReturnType<typeof AiGenerateText> {
  const { generateText: aiGenerateText } = await import('ai')
  return aiGenerateText(await applySeal(params))
}

/**
 * Drop-in replacement for the Vercel AI SDK `streamText`, accepting one extra
 * field: `retrieved`. Untrusted content is sealed before the model call.
 *
 * Note: unlike the SDK's synchronous `streamText`, this returns a Promise
 * because sealing is async.
 */
export async function streamText(
  params: WithRetrieved<StreamTextParams>,
): Promise<ReturnType<typeof AiStreamText>> {
  const { streamText: aiStreamText } = await import('ai')
  return aiStreamText(await applySeal(params))
}
