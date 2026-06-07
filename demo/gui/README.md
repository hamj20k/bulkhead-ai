# Bulkhead demo GUI

A tiny local web page that runs the **same prompt against a real model twice** —
once as the raw "soup," once sealed with bulkhead — side by side. Pick a model,
pick a prebuilt sample (or type your own), hit Run.

Zero frontend framework. The server is Python stdlib. Model calls happen
**server-side**, so your API key never reaches the browser. It uses the real
local `bulkhead` package to build the sealed request.

The right/protected side uses the current config from the **Setup & test
terminal**. If you have not saved a config, it uses the lightest default:
Bulkhead's local regex scorer (model-free, zero setup). Configure a gate or
judge model on `/setup` for heavier-duty detection, then run the single demo or
Smoke Test with those exact settings.

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

## Setup & test terminal (`/setup`)

Open **http://127.0.0.1:8000/setup** for a guided, terminal-style page to set up
and test the 0.2 tiered scorer end to end, all from the browser (server-side on
localhost):

- **Environment** panel — shows OS, which extras/SDKs are installed, whether
  Ollama is installed/running, which API keys are set, and the current config.
- **Install backends** — buttons that stream live output: install Ollama (uses
  winget / brew / curl per OS), `ollama pull <model>`, and `pip install` an extra
  (`onnx` / `llama` / `transformers` / provider SDKs).
- **API keys** — save a provider key into `.env` (gitignored) under the chosen
  env var; it's loaded into the running server immediately.
- **Configure** — pick the gate runtime + model, judge runtime + model/provider,
  `judge_when`, and policy; writes the Bulkhead config file.
- **Test** — paste an instruction plus retrieved chunks (one per line, so you can
  split an attack across lines to exercise the cross-chunk judge) and see the
  risk score, flags, whether it was blocked, and the sealed JSON payload.

It uses the real local package (`packages/python`) and the same `seal()` /
config / scorer code paths the library ships.

## What you'll see

- **Left (Without Bulkhead):** instruction + content concatenated into one user
  message. With an attack sample, the injection often lands — watch for the
  `injection risk` badge.
- **Right (With Bulkhead):** the current saved setup config scores first. If it
  blocks, no protected prompt is sent to the base model; otherwise the model gets
  JSON input with `trusted_instruction` and `untrusted_inputs`, plus a guard in
  `system`.
- **Smoke Test:** select one or more relevant chat models and run every sample.
  The dashboard uses the current setup config for every protected run and shows
  progress, errors, verdicts, full prompt messages, and model outputs for each
  model/sample pair. If Bulkhead flags or blocks the protected side, the
  protected model output is hidden and the score/risk level is shown instead.
  Verdicts are keyword-marker checks, so they are illustrative and can be
  inaccurate. They ignore text inside
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
