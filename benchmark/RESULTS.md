# Bulkhead ASR benchmark results

> ⚠️ **STALE — regenerate.** These numbers predate the corrected success metric
> (refusal-aware), the `sealed_strict` row, and the per-style breakdown. Re-run
> `python benchmark/asr.py --trials 3 --log-responses` to refresh. The old metric
> counted "marker present" as a success even when the model *refused while quoting
> the injection*, which over-counts attacks in the sealed modes — so the corrected
> `sealed_user` number should come out **lower** than the 45% below.

- model: `llama-3.1-8b-instant`  ·  payloads: 31  ·  trials: 3  ·  runs/mode: 93
- generated: 2026-06-04
- scoring/gating disabled (permissive) to isolate the *structural* effect.

**Attack Success Rate (marker appeared in the response) — lower is better:**

| mode | ASR |
|------|-----|
| `soup` (no bulkhead) | 65% |
| `sealed_user` (bulkhead default — retrieved in user/data msg) | 45% |
| `sealed_system` (legacy — retrieved in system) | 54% |

> ASR is model-dependent, non-deterministic, and small-n. This shows *reduction*, not elimination. Numbers regenerate with `python benchmark/asr.py`.
