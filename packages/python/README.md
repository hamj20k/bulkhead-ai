# bulkhead-ai (Python)

Tiny library for separating trusted prompts from untrusted RAG/tool content.

It stops external content (web pages, RAG results, tool outputs) from ever being treated as instructions, by separating the trusted **USER** bucket from the untrusted **RETRIEVED** bucket before anything reaches the model.

## Install

```bash
pip install bulkhead-ai            # core, zero dependencies
pip install bulkhead-ai[openai]    # + OpenAI wrapper
pip install bulkhead-ai[anthropic] # + Anthropic wrapper
pip install bulkhead-ai[all]       # everything
```

## The problem

```python
# The "soup": instructions and untrusted data concatenated into one string.
# A web page that says "ignore previous instructions" has full instruction authority.
messages = [{"role": "user", "content": f"{user_prompt}\n\n{web_content}"}]
```

## The fix

```python
from bulkhead import seal
from bulkhead.wrappers.openai_wrapper import create_completion

# Recommended: the wrapper builds the correct messages=[...] shape for you.
response = create_completion(
    client,
    user=user_prompt,        # USER bucket — passed through untouched
    retrieved=web_content,   # RETRIEVED bucket — scored and sealed as JSON
    model="gpt-4o",
)
```

Or seal once and shape it for your SDK — each SDK expects a different shape:

```python
sealed = seal(user=user_prompt, retrieved=web_content)

# OpenAI — guard in system; JSON payload in a user/data-position message
client.chat.completions.create(
    model="gpt-4o",
    messages=sealed.to_messages(),
)

# Anthropic — guard in the top-level system; JSON payload in the user turn
client.messages.create(
    model="claude-haiku-4-5-20251001",
    **sealed.to_anthropic_params(),
)
```

> **Where each bucket goes.** The untrusted `retrieved` content is always placed in
> `untrusted_inputs` inside a `user`-role JSON message, **never `system`**.
> `system` holds only a trusted guard preamble, and your instruction stays
> authoritative as `trusted_instruction`.
>
> `**seal()` unpacks to `{"messages": [...]}` (OpenAI shape), so
> `client.chat.completions.create(model=..., **sealed)` works directly. For Anthropic
> use `to_anthropic_params()` (its API can't take consecutive user messages).

## API

### `seal(user, retrieved, config=None) -> SealOutput`

- `user: str` — the instruction. Untouched.
- `retrieved: str | list[str]` — untrusted external content. Scored and sealed.
- `config: BulkheadConfig | None`
- Returns a `SealOutput` with fields `instruction`, `data` (the JSON payload,
  `""` if none), `guard`, plus `.to_messages()` (OpenAI),
  `.to_anthropic_params()` (Anthropic), and `**` unpacking (→ OpenAI
  `messages`). `.prompt` is a back-compat alias of `instruction`.

### `Bulkhead(config).seal(...)` / `Bulkhead(config).session()`

A session accumulates `risk_history` across turns for observability. Each turn is scored and gated independently (track-only).

```python
from bulkhead import Bulkhead, BulkheadConfig

session = Bulkhead(BulkheadConfig(policy="strict")).session()
for turn in agent_loop:
    sealed = session.seal(user=turn.prompt, retrieved=turn.external_content)
    ...  # session.risk_history grows each turn
```

### Policy modes

| mode | behavior at `score >= threshold` (default 0.7) |
|------|-----------------------------------------------|
| `strict` | raises `BulkheadInjectionError`, call blocked |
| `warn` (default) | emits `UserWarning`, call proceeds |
| `permissive` | annotates only, never blocks |

```python
BulkheadConfig(policy="strict", scorer=ScorerConfig(threshold=0.7, check_unicode=True))
```

> The built-in scorer adds **0.3 per matched pattern** (capped at 0.9), so a single
> textbook match scores `0.3` — it raises a flag but does **not** cross the default
> `0.7` block threshold. Treat the block as a coarse safety net; for real detection,
> pass your own `scorer=` (e.g. an LLM judge).

### Wrappers

```python
from bulkhead.wrappers.openai_wrapper import create_completion
from bulkhead.wrappers.anthropic_wrapper import create_message
```

Legacy single-string LangChain `chain.run()` is intentionally unsupported
because it flattens system, trusted instruction, and untrusted data into one
string.

## How it works

Every call generates cryptographic IDs (`secrets.token_hex`), scores each
retrieved source with a local regex/heuristic scorer (no ML, no network),
applies the policy gate, then emits a JSON user message:

```json
{
  "trusted_instruction": "Summarise this article.",
  "untrusted_inputs": [
    {"id": "...-1", "risk": 0.3, "flags": ["injection_pattern"], "content": "..."}
  ]
}
```

The system guard states that only `trusted_instruction` is authoritative and
that `untrusted_inputs` is source material only.

Zero core dependencies. Pure Python standard library. Python 3.9+.

> **Defense-in-depth, not a silver bullet.** The JSON structure is a strong hint,
> not an enforced wall — LLMs have no hard system/data boundary, and the built-in
> regex scorer is a heuristic pre-filter, not a detector. Swap in your own scorer
> (`Bulkhead(config, scorer=my_detector)`) and see the root
> [threat model](../../README.md#threat-model).

## License

MIT © Hamza Jawad
