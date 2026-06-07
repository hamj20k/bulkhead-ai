# Roadmap

Bulkhead is meant to stay small. The roadmap is about better defaults and more
integration coverage, not a giant framework.

## Shipped in 0.2

- Tiered scorer: a per-chunk **gate** and a cross-chunk **judge** on top of the
  regex default, with `judge_when`, `judge_on_error`, judge caching, and `aseal()`.
- Judge/gate backends: cloud (OpenAI / Groq / Anthropic), Ollama, ONNX encoder
  gate, llama-cpp GGUF judge, transformers gate. JS ships cloud + Ollama judges.
- `bulkhead setup` CLI (Python): installs Ollama, pulls models, `pip install`s
  extras, writes config; plus `bulkhead status` and `Bulkhead.from_config()`.
- Strengthened the zero-dep regex scorer (Trojan-Source bidi, Unicode tag chars,
  JSON field-spoofing, action-verb density, long encoded blobs, more phrasings).
- npm + PyPI publishing via trusted publishing (0.1.1).

## Near term

- More SDK wrappers that preserve structured message boundaries.
- Expand the benchmark/smoke-test corpus with realistic RAG, support, browser,
  and tool outputs; report `sealed_judge` numbers across models.
- Document scorer false positives/negatives more thoroughly; calibrate the gate.
- JS parity for a local gate and the config-driven CLI install flow.
- Real-runtime CI coverage for the ONNX / llama-cpp backends.

## Later

- A native async seal path beyond `aseal()` for high-throughput servers.
- Framework adapters for common retrieval and agent stacks.
- Few-shot / fine-tuned judge prompt presets per model size.

## Non-goals

- No claim that Bulkhead makes prompt injection impossible.
- No runtime network calls in the core package.
- No heavyweight guardrails framework inside the small package.
