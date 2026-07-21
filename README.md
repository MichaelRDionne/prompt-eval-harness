# prompt-eval-harness

![CI](https://github.com/MichaelRDionne/prompt-eval-harness/actions/workflows/tests.yml/badge.svg)
![Weekly eval](https://github.com/MichaelRDionne/prompt-eval-harness/actions/workflows/eval.yml/badge.svg)

A small, dependency-free harness for scoring prompts against a rubric of
deterministic checks — so a prompt edit gets regression-tested like a code
edit, instead of eyeballed.

Evaluation-first prompt development starts from one observation: **an output
that reads fluently and an output that is correct are different things, and
eyeballing cannot reliably tell them apart.** This repo exists to close that
gap with checks that run in milliseconds and don't get tired of reading the
tenth diff of the day.

## The demo is the test suite

`tests/test_harness.py` runs two mock "models" against the same synthetic
incident-summary task:

- `good_model` — terse, faithful. Passes 5/5 checks.
- `fluent_but_wrong_model` — reads *better* than the good one. It also drops
  the exact error code, invents a root cause that never happened, and
  launders a precise impact figure into vague reassurance. Weighted score:
  **9%**.

Both look fine in a quick read. That asymmetry — polish up, correctness down —
is the standard failure mode of iterating on prompts by vibes, and it is
exactly what a weighted rubric catches for free on every edit.

The same pattern shows up in `examples/generic_eval.jsonl`, scored live by
`scripts/run_eval.py`: a fluent changelog summary that quietly drops a
breaking-change notice, a JSON extraction that hallucinates a field nobody
asked for, a ticket summary that folds under a prompt-injection line buried
in the input, and a performance recap that rounds away the one figure the
task said to keep exact. Every case is a version of the same trap.

## How it works

Cases are JSONL, one per line:

```json
{"id": "keeps-error-code", "input": "<incident text>", "checks": {"must_include": ["ERR_429"]}, "weight": 3}
```

Checks are pure functions, no API keys required:

| check | catches |
|---|---|
| `must_include` | dropped facts (the error code, the exact figure, the required field) |
| `must_not_include` | hallucinated content, leaked instructions |
| `must_match` | format contracts (regex) |
| `max_words` | verbosity creep |
| `valid_json` | broken structured output (tolerates ```json fences) |

A target is any callable `(prompt, case_input) -> output` — a raw model call,
a chain, or a mock. Run and gate:

```python
from evalharness.runner import load_cases, run_eval

report = run_eval(prompt, load_cases("examples/generic_eval.jsonl"), target)
print(report.to_markdown())
assert report.gate(0.9), "prompt regression"
```

Weights make the score mean something: dropping a breaking-change notice
(weight 3) is not the same defect as running five words over budget
(weight 1).

## Design choices

- **Deterministic layer first.** LLM-graded rubrics have their place, but they
  add cost, latency, and their own failure modes. Most regressions that
  matter in structured text-generation work — dropped facts, invented facts,
  broken formats — are catchable with string and JSON checks that run in
  milliseconds, keyless, in CI.
- **Weights are severity.** The report's number should move most when the
  worst thing breaks.
- **Cases are data, not code.** JSONL cases can be reviewed by a domain
  expert who doesn't read Python — in high-stakes work, that review *is*
  the eval.

## Run it

```bash
pip install pytest
python -m pytest tests/ -v
```

## Live scoring + CI gate

`examples/generic_eval.jsonl` is a fully domain-neutral suite (changelog
summarization, JSON extraction, format compliance, prompt-injection
resistance, precision preservation) that `scripts/run_eval.py` scores on
demand:

```bash
python scripts/run_eval.py
```

It targets the real model (`claude-haiku-4-5-20251001`, via the `anthropic`
SDK) when `ANTHROPIC_API_KEY` is set, and otherwise falls back to a
deterministic mock — no key required to see the gate do something meaningful.
Every run appends a row to [`benchmarks/results.jsonl`](benchmarks/results.jsonl)
and regenerates the scorecard below.

<p align="center"><img src="benchmarks/scorecard.svg" alt="Eval scorecard" width="420"></p>

`.github/workflows/tests.yml` runs the test suite (including the eval gate) on
every push; `.github/workflows/eval.yml` runs the live suite weekly and
commits the updated results/scorecard back to the repo.

### Demo

![demo](assets/demo.gif)

The recording shows a fluent-but-wrong deterministic run failing the gate,
then a fully compliant run passing it — generated with
[VHS](https://github.com/charmbracelet/vhs) from `assets/demo.tape`.

All example content is synthetic. No production data, no real prompts or
outputs from any deployed system.

MIT license.
