# Contributing

Thanks for helping make Bulkhead better. The project is small on purpose: keep
changes focused, keep the security claims honest, and make the safe path easy to
use.

## Good first contributions

- Add wrappers for popular SDKs without flattening trusted and untrusted content
  into one string.
- Improve the zero-dep regex scorer while documenting false positives and
  negatives (it now flags injection phrasing, bidi/tag unicode, field-spoofing,
  action density, and encoded blobs — add more high-precision signals).
- Add or improve a judge/gate backend (see `packages/python/bulkhead/scorers/`):
  a new provider, a better default judge prompt, or JS parity for a local gate.
- Tune the few-shot `JUDGE_PROMPT` for small local models.
- Add smoke-test / benchmark samples for common RAG, browser, tool, and
  support-ticket workflows (incl. cross-chunk split payloads).
- Improve docs, examples, and package ergonomics.

## Local setup

### JavaScript

```bash
cd packages/js
npm install
npm run typecheck
npm run test:run
npm run build
```

### Python

```bash
cd packages/python
python -m pip install --upgrade pip pytest build
python -m pytest -q
python -m build
```

## Pull requests

- Open an issue first for large API, policy, or threat-model changes.
- Include tests for behavior changes.
- Avoid claims that Bulkhead "solves" prompt injection. The honest claim is
  defense-in-depth through structural separation plus optional scoring.
- Do not add runtime network calls or model calls to the core packages.
- Keep untrusted content in JSON `untrusted_inputs`; never place it in `system`.

## Release process

Maintainers publish from GitHub Actions by creating a GitHub release. The release
workflow runs tests, builds both packages, and publishes through npm/PyPI trusted
publishing once those registries are configured.
