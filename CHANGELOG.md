# Changelog

All notable changes to Bulkhead will be documented here.

## 0.2.0

- Tiered scorer: the regex default now sits under an optional per-chunk **gate**
  and an optional cross-chunk **judge** that sees all retrieved chunks together
  (catches payloads split across chunks). `judge_when` controls escalation
  (default `suspicious_or_many`); judge verdicts are cached.
- `judge_on_error` failure mode (`fail_open`/`fail_closed`, default follows
  policy, never silent) with a `judge_timeout`.
- `aseal()`: async-native companion to `seal()` for asyncio servers; `seal()` is
  unchanged. (JS `seal()` was already async.)
- Strengthened the zero-dep regex scorer (no new deps): many more injection /
  jailbreak / prompt-extraction phrasings, and new flags `bidi_control`
  (Trojan-Source), `tag_chars` (Unicode tag-block smuggling), `field_spoof`
  (forging Bulkhead's own JSON fields), `action_density` (state-change verbs),
  and `possible_encoding` (long base64/hex blobs).
- Judge backends: cloud (OpenAI/Groq/Anthropic, sync+async), Ollama (sync+async),
  local ONNX encoder gate, and llama-cpp GGUF judge. JS ships cloud + Ollama
  judge factories (`cloudJudge`, `ollamaJudge`).
- `bulkhead setup` CLI (Python): `--recommended`, interactive wizard, `status`,
  `--reset`, with size warnings, progress, and smoke-test confirmation. Config is
  opt-in via `Bulkhead.from_config()`; plain `seal()` is unchanged.
- New extras: `[onnx]`, `[llama]`, `[transformers]`, `[ollama]`. Model weights
  download on first use, never bundled.

## 0.1.1

- First PyPI release; automated publishing via trusted publishers (npm OIDC + PyPI).
- Added `.env.example` to make the demo/GUI key setup work out of the box.
- Expanded README: explicit GUI setup, guidance on routing tool/web/file/DB output
  through `retrieved`, and a reference to the model smoke-test PDF.
- Added GitHub issue and pull-request templates.

## 0.1.0 - Initial public alpha

- Added JavaScript/TypeScript package with Vercel AI SDK wrapper.
- Added Python package with OpenAI and Anthropic helpers.
- Added JSON field separation for `trusted_instruction` and `untrusted_inputs`.
- Added local heuristic injection-risk scoring and policy gating.
- Added GUI smoke-test demo with model comparison and output dashboard.
- Added benchmark/demo material and threat-model documentation.
