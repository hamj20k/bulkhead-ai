# Bulkhead demo GUI

A tiny local web page that runs the **same prompt against a real model twice** —
once as the raw "soup," once sealed with bulkhead — side by side. Pick a model,
pick a prebuilt sample (or type your own), hit Run.

Zero frontend framework. The server is Python stdlib. Model calls happen
**server-side**, so your API key never reaches the browser. It uses the real
local `bulkhead` package to build the sealed request.

## Providers

The backend is chosen by the model id:

| Model id | Backend | Needs |
|----------|---------|-------|
| Groq chat/completion models such as `llama-3.1-8b-instant`, `llama-3.3-70b-versatile`, `meta-llama/llama-4-scout-17b-16e-instruct`, `qwen/qwen3-32b`, `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `groq/compound`, `groq/compound-mini` | Groq | `GROQ_API_KEY`, `pip install groq` |
| `claude-haiku-4-5-20251001`, `claude-sonnet-4-6` | Anthropic | `ANTHROPIC_API_KEY`, `pip install anthropic` |

You can also type any other model id for the matching provider.

## Run

```bash
cp .env.example .env            # then paste your key(s) into .env
pip install groq anthropic      # install whichever provider(s) you'll use
python demo/gui/app.py          # → open http://127.0.0.1:8000
```

Keys are read from `.env` (repo root or this folder) or the environment — `.env`
is gitignored. You only need the key for the provider you pick; if it's missing,
the UI shows a clear error instead of crashing.

## What you'll see

- **Left (❌ Without Bulkhead):** instruction + content concatenated into one user
  message. With an attack sample, the injection often lands — watch for the
  `injection risk` badge.
- **Right (🛡️ With Bulkhead):** JSON input with `trusted_instruction` and
  `untrusted_inputs`, plus a guard in `system`. Expand **"view messages sent"**
  to see the structure.
- **Smoke Test:** select one or more relevant chat models and run every sample.
  The dashboard shows progress, errors, verdicts, full prompt messages, and both
  model outputs for each model/sample pair. Verdicts ignore text inside
  `<think>...</think>` blocks and explicit reasoning/rationale sections, but the
  raw output remains visible as separate output vs. thinking/reasoning sections.
  Badges score only the output section. You can print the results or save a text
  summary with aggregate stats.
- **Sealed format:** the protected side sends a JSON payload with
  `trusted_instruction` and `untrusted_inputs` fields.

The badge checks whether each sample's attack marker leaked into the response.
It's illustrative and non-deterministic — small models can still be injected even
when sealed (Bulkhead is defense-in-depth, not a guarantee; see the root
[threat model](../../README.md#threat-model)).

Edit `SAMPLES` or `MODEL_OPTIONS` in [`index.html`](index.html) to add your own.
