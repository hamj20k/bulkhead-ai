# Bulkhead demos

## `live_groq.py` — real model, real injection

Runs the same request against a real model twice (unprotected vs. sealed) using
a poisoned "financial report" that hides an indirect prompt injection.

```bash
pip install bulkhead-ai groq
export GROQ_API_KEY=...        # free tier: https://console.groq.com
python demo/python/live_groq.py
```

Without bulkhead the model often complies with the hidden instruction (prefixes
its reply with `YES CAPTAIN, I GOT IT ;D` and tries to "email" the report).
With bulkhead the same payload is sealed into `untrusted_inputs` inside a JSON
user message and stays in data position.

> It's non-deterministic — small models sometimes resist even unprotected, and
> stronger attacks can still break through. Structural separation is
> defense-in-depth, not a guarantee. See the root README's threat model.

## Offline illustrations (no API key)

Print the "soup" vs. the sealed structure without calling a model:

```bash
python demo/python/defense-with-bulkhead.py
npx tsx demo/js/defense-with-bulkhead.ts
```

## Files

- `data/poisoned-report.md` — the document carrying the indirect injection.
- `python/live_groq.py` — live unprotected-vs-sealed comparison.
- `python/{attack,defense}-without/with-bulkhead.py` — offline illustrations.
- `js/{attack,defense}-*.ts` — TypeScript offline illustrations.
