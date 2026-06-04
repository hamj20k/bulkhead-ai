# Changelog

All notable changes to Bulkhead will be documented here.

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
