import { describe, expect, it, vi } from 'vitest'
import { generateText } from '../wrappers/vercel-ai'

vi.mock('ai', () => ({
  generateText: vi.fn((params) => params),
  streamText: vi.fn((params) => params),
}))

describe('vercel-ai wrapper', () => {
  it('preserves trusted messages inside trusted_instruction', async () => {
    const result = (await generateText({
      // The real SDK accepts messages; the wrapper must not drop them.
      messages: [{ role: 'user', content: 'Summarise this.' }],
      retrieved: 'external content',
      model: {} as never,
    })) as unknown as { messages: Array<{ content: string }> }

    const payload = JSON.parse(result.messages[0]!.content)
    expect(payload.trusted_instruction).toContain('Summarise this.')
    expect(payload.untrusted_inputs[0].content).toBe('external content')
    expect(result.messages).toHaveLength(1)
  })
})
