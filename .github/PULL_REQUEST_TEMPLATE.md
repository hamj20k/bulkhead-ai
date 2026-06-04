## What changed?

## Why?

## Tests

- [ ] JS: `npm run typecheck && npm run test:run && npm run build`
- [ ] Python: `python -m pytest -q`
- [ ] Not applicable

## Security/separation checklist

- [ ] Untrusted content remains in `untrusted_inputs`, never `system`.
- [ ] The change does not flatten trusted and untrusted content into prompt soup.
- [ ] Any new security claim is documented as defense-in-depth, not a guarantee.
