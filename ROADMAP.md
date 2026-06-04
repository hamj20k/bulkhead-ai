# Roadmap

Bulkhead is meant to stay small. The roadmap is about better defaults and more
integration coverage, not a giant framework.

## Near term

- Add more SDK wrappers that preserve structured message boundaries.
- Expand the smoke-test corpus with realistic RAG, support, browser, and tool
  outputs.
- Improve scorer calibration and document known false positives/negatives.
- Add package publishing through GitHub trusted publishing.
- Add examples for strict policy, custom scorers, and audit logging.

## Later

- Optional LLM-judge scorer interface examples.
- More benchmark reporting across model families.
- Framework adapters for common retrieval and agent stacks.
- Signed/provenance-aware release artifacts.

## Non-goals

- No claim that Bulkhead makes prompt injection impossible.
- No runtime network calls in the core package.
- No heavyweight guardrails framework inside the small package.
