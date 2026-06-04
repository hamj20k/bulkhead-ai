# bulkhead-ai

Tiny library for separating trusted prompts from untrusted RAG/tool content.

Stops external content from ever being treated as instructions by separating the trusted **USER** bucket from the untrusted **RETRIEVED** bucket before anything reaches the model.

## Install

```bash
npm install bulkhead-ai ai
```

`ai` (the Vercel AI SDK) is a peer dependency.

## Before / after

```ts
// ❌ The "soup": instructions and untrusted data in one string.
// A page that says "ignore previous instructions" has full instruction authority.
const result = await generateText({
  model: openai('gpt-4o'),
  prompt: `${userPrompt} ${webContent}`,
})
```

```ts
// ✅ Swap one import, add one field.
import { generateText } from 'bulkhead-ai'

const result = await generateText({
  model: openai('gpt-4o'),
  prompt: userPrompt,    // USER bucket — passed through untouched
  retrieved: webContent, // RETRIEVED bucket — scored and sealed as JSON
})
```

## API

### `seal(input): Promise<SealOutput>`

Low-level primitive. Returns `{ system, messages }` that spreads into the Vercel AI SDK. The untrusted retrieved content is placed in `untrusted_inputs` inside a JSON `user`-role (data-position) message — **never `system`**. `system` holds only a trusted guard preamble; the instruction stays authoritative as `trusted_instruction`.

```ts
import { Bulkhead } from 'bulkhead-ai'

const bulkhead = new Bulkhead({ policy: 'strict' })
const result = await generateText({
  model: openai('gpt-4o'),
  ...(await bulkhead.seal({ user: userPrompt, retrieved: webContent })),
  // → { system: <guard>, messages: [ {user: <json payload>} ] }
})
```

- `user: string` — the instruction. Untouched, authoritative.
- `retrieved: string | string[]` — untrusted external content. Each source is scored and placed in `untrusted_inputs`.

### Sessions (multi-turn agents)

```ts
const session = new Bulkhead({ policy: 'strict' }).session()
for (const turn of agentLoop) {
  const result = await generateText({
    model: openai('gpt-4o'),
    ...(await session.seal({ user: turn.prompt, retrieved: turn.externalContent })),
  })
}
// session.riskHistory accumulates a RiskResult per turn (observability).
```

Each turn is scored and gated independently; the session records history but does not change gating behavior across turns.

### Policy modes

| mode | behavior at `score >= threshold` (default 0.7) |
|------|-----------------------------------------------|
| `strict` | throws `BulkheadInjectionError`, call blocked |
| `warn` (default) | `console.warn`, call proceeds |
| `permissive` | annotates only, never blocks |

```ts
new Bulkhead({ policy: 'strict', scorer: { threshold: 0.7, checkUnicode: true } })
```

> The built-in scorer adds **0.3 per matched pattern** (capped at 0.9), so a single
> textbook match scores `0.3` — it raises a flag but does **not** cross the default
> `0.7` block threshold (that needs ~3 weak hits or one strong/custom signal). Treat
> the block threshold as a coarse safety net; for real detection, plug in a scorer.

## Caveats

- **`streamText` returns a `Promise`.** Unlike the Vercel SDK's synchronous `streamText`, the wrapped version is `async` (sealing — and any custom scorer — may be async). Use `const result = await streamText({ ... })`.

## How it works

Each call generates cryptographic IDs (`crypto.randomBytes`), scores each retrieved source with a local regex/heuristic scorer (no ML, no network), applies the policy gate, then emits a JSON user message:

```json
{
  "trusted_instruction": "Summarise this article.",
  "untrusted_inputs": [
    {"id": "...-1", "risk": 0.3, "flags": ["injection_pattern"], "content": "..."}
  ]
}
```

The system guard states that only `trusted_instruction` is authoritative and that `untrusted_inputs` is source material only.

Zero runtime dependencies. ESM + CJS. TypeScript strict.

> **Defense-in-depth, not a silver bullet.** The JSON structure is a strong hint, not an enforced wall — LLMs have no hard system/data boundary, and the built-in regex scorer is a heuristic pre-filter, not a detector. Swap in your own scorer (`new Bulkhead(config, myScorer)` — sync or async) and see the root [threat model](../../README.md#threat-model).

## Contributing

```bash
npm install
npm run typecheck
npm run test:run
npm run build
```

## License

MIT © Hamza Jawad
