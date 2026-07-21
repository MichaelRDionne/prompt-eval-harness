# prompt-eval-harness

A small, dependency-free harness for scoring prompts against a rubric of
deterministic checks — so a prompt edit gets regression-tested like a code
edit, instead of eyeballed.

Written by a clinician who builds AI workflows for clinical documentation and
got burned by the gap this repo exists to close: **an output that reads
fluently and an output that is correct are different things, and eyeballing
cannot reliably tell them apart.**

## The demo is the test suite

`tests/test_harness.py` runs two mock "models" against the same synthetic
intake-summarization task (invented patient, invented facts):

- `good_model` — terse, faithful. Passes 5/5 checks.
- `fluent_but_wrong_model` — reads *better* than the good one. It also drops
  the penicillin allergy, swaps prazosin for a hallucinated trazodone, and
  launders "2-3 beers most nights" into "occasional social drinking."
  Weighted score: **9%**.

Both look fine in a quick read. That asymmetry — polish up, correctness down —
is the standard failure mode of iterating on prompts by vibes, and it is
exactly what a weighted rubric catches for free on every edit.

## How it works

Cases are JSONL, one per line:

```json
{"id": "keeps-allergy", "input": "<note text>", "checks": {"must_include": ["penicillin"]}, "weight": 3}
```

Checks are pure functions, no API keys required:

| check | catches |
|---|---|
| `must_include` | dropped facts (the allergy, the dose, the safety flag) |
| `must_not_include` | hallucinated content, leaked instructions |
| `must_match` | format contracts (regex) |
| `max_words` | verbosity creep |
| `valid_json` | broken structured output (tolerates ```json fences) |

A target is any callable `(prompt, case_input) -> output` — a raw model call,
a chain, or a mock. Run and gate:

```python
from evalharness.runner import load_cases, run_eval

report = run_eval(prompt, load_cases("examples/intake_summary.jsonl"), target)
print(report.to_markdown())
assert report.gate(0.9), "prompt regression"
```

Weights make the score mean something: dropping an allergy (weight 3) is not
the same defect as running five words over budget (weight 1).

## Design choices

- **Deterministic layer first.** LLM-graded rubrics have their place, but they
  add cost, latency, and their own failure modes. Most regressions that matter
  in structured clinical-adjacent work — dropped facts, invented facts, broken
  formats — are catchable with string and JSON checks that run in
  milliseconds, keyless, in CI.
- **Weights are severity.** The report's number should move most when the
  worst thing breaks.
- **Cases are data, not code.** JSONL cases can be reviewed by a domain expert
  who doesn't read Python — in clinical work, that review *is* the eval.

## Run it

```bash
pip install pytest
python -m pytest tests/ -v
```

All example content is synthetic. No patient data, no production prompts.

MIT license.
