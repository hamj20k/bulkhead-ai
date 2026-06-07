# Versions

A per-version record of what Bulkhead shipped, what changed, and how to use it.
For the terse list see [CHANGELOG.md](CHANGELOG.md); this file is the narrative.

Bulkhead is published to npm (`bulkhead-ai`) and PyPI (`bulkhead-ai`). The two
packages track the same version number and the same core behavior; where they
differ it is called out.

---

## 0.2.0 — Tiered scorer + `bulkhead setup`

The big release. The single weak regex scorer became a **tiered, plug-and-play
scoring system**, while the zero-dep regex path stays the instant default.

### What it has
- Everything from 0.1.x (structural separation, JSON fields, policy modes,
  wrappers, the Claude Code skill).
- **Three scoring tiers** you opt into:
  - **regex** (default, zero-dep) — now much stronger (see "Added" below).
  - **gate** — a cheap per-chunk classifier (e.g. a local ONNX model).
  - **judge** — a model that sees *all* retrieved chunks at once, to catch
    payloads split across chunks.
- **`judge_when`** escalation: `never` / `gate_flagged` / `suspicious_or_many`
  (default) / `always`.
- **`judge_on_error`** failure mode: `fail_open` / `fail_closed` / `auto`
  (follows policy). Never silent — a judge error always logs a warning. Plus
  `judge_timeout`.
- **`aseal()`** — async-native twin of `seal()` for asyncio servers (FastAPI,
  Starlette). `seal()` is unchanged. (JS `seal()` was already async.)
- **Judge/gate backends**: cloud (OpenAI / Groq / Anthropic, sync+async), Ollama
  (sync+async), local ONNX encoder gate, llama-cpp GGUF judge. JS ships
  `cloudJudge` and `ollamaJudge` factories.
- **`bulkhead setup` CLI** (Python): `--recommended`, an interactive wizard,
  `bulkhead status`, and `bulkhead setup --reset`. Writes a JSON config; opt in
  with `Bulkhead.from_config()`.
- New install extras: `[onnx]`, `[llama]`, `[transformers]`, `[ollama]`,
  plus the existing `[openai]` / `[anthropic]`.

### Added since 0.1.1
- Cross-chunk **judge** hook + `judge_when` (with a combined-text pre-pass that
  is the only trigger able to catch pure cross-chunk splits) + judge result cache.
- `judge_on_error` + `judge_timeout`.
- `aseal()` (Python).
- **Strengthened the zero-dep regex scorer** (no new deps): many more
  injection / jailbreak / prompt-extraction phrasings; new flags
  `bidi_control` (Trojan-Source reordering), `tag_chars` (Unicode tag-block
  smuggling), `field_spoof` (text trying to forge Bulkhead's own
  `trusted_instruction` / `untrusted_inputs` JSON), `action_density` (several
  distinct state-change verbs), and `possible_encoding` (long base64 / hex
  blobs). Weights tuned so a single benign hit flags but does not block.
- Config file + `from_config()` + a runtime registry.
- The cloud / Ollama / ONNX / llama-cpp backends and the `bulkhead setup` CLI.
- Invariant kept: a plain `pip install bulkhead-ai` + `seal()` behaves exactly
  as in 0.1.x — regex default, zero deps, no network.

### How to use
Default (unchanged, zero-dep):
```python
from bulkhead import seal
seal(user=prompt, retrieved=web)            # regex scoring, no setup
```
Add a stronger scorer via the CLI (Python):
```bash
pip install "bulkhead-ai[onnx,ollama]"
bulkhead setup --recommended                # ONNX gate + Ollama judge
```
```python
from bulkhead import Bulkhead
bh = Bulkhead.from_config()                 # opt-in
sealed = bh.seal(user=prompt, retrieved=chunks)
```
Wire a judge directly (no config file):
```python
from bulkhead import Bulkhead, BulkheadConfig
from bulkhead.scorers.ollama import ollama_judge_factory
judge = ollama_judge_factory({"model": "llama3.2:3b"}, BulkheadConfig())
bh = Bulkhead(BulkheadConfig(policy="strict"), judge=judge)
```
```ts
import { Bulkhead, ollamaJudge } from 'bulkhead-ai'
const bh = new Bulkhead({ policy: 'strict' }, undefined, ollamaJudge({ model: 'llama3.2:3b' }))
```
Async server (Python): use `aseal()` once a judge is configured:
```python
sealed = await bh.aseal(user=prompt, retrieved=chunks)
```

### Notes / caveats
- Plain `seal()`/`Bulkhead()` never read the config file; config is opt-in via
  `Bulkhead.from_config()` (keeps default behavior pure, no hidden network).
- A **cloud** judge sends retrieved content to the provider; local runtimes keep
  it on your machine. `bulkhead setup` says so before you pick cloud.
- The ONNX and llama-cpp backends require their extras and download a model on
  first use; weights are never bundled.

---

## 0.1.1 — Docs, packaging, first automated release

### What it has
Same library as 0.1.0, with the publishing pipeline and docs sorted out.

### Added since 0.1.0
- First **PyPI** release; automated publishing for both npm + PyPI via trusted
  publishing (OIDC), no long-lived tokens.
- `.env.example` so the demo / GUI key setup works out of the box.
- Expanded README: explicit GUI setup, guidance on routing tool/web/file/DB
  output through `retrieved`, reference to the model smoke-test PDF.
- Packaged the auditor as a discoverable Claude Code skill at
  `.claude/skills/bulkhead/SKILL.md` (was a loose `skill/bulkhead.md`).
- GitHub issue + PR templates; emojis removed from README/docs.

### How to use
```bash
npm install bulkhead-ai ai      # JS
pip  install bulkhead-ai        # Python
```
```python
from bulkhead import seal
client.chat.completions.create(model="gpt-4o", messages=seal(user=p, retrieved=web).to_messages())
```

---

## 0.1.0 — Initial public alpha

### What it has
- The core idea: structural separation of a trusted instruction from untrusted
  retrieved content, using explicit JSON fields (`trusted_instruction` /
  `untrusted_inputs`) placed in a user/data-position message, never `system`.
- A local heuristic injection-risk score + policy gating (`strict` / `warn` /
  `permissive`).
- JavaScript/TypeScript package with a Vercel AI SDK drop-in wrapper; Python
  package with OpenAI and Anthropic helpers (`to_messages()`,
  `to_anthropic_params()`).
- The language-agnostic Claude Code auditing skill.
- Zero runtime deps in the core; no network or model calls.

### How to use
```ts
import { generateText } from 'bulkhead-ai'   // was: 'ai'
await generateText({ model: openai('gpt-4o'), prompt: userPrompt, retrieved: webContent })
```
```python
from bulkhead import seal
seal(user=prompt, retrieved=web)
```
