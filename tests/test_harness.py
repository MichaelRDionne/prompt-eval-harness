"""The demo IS the test suite: two mock 'models' answer the same synthetic
clinical-summary task. Both outputs read fluently. One fails the eval.

That is the whole argument for evaluation-first prompt work — eyeballing
cannot tell these apart reliably, and a rubric can.
"""

import pytest

from evalharness.checks import run_checks, valid_json
from evalharness.runner import EvalReport, load_cases, run_eval

# Synthetic intake note — invented patient, invented content.
INTAKE = (
    "58yo veteran, PTSD and insomnia. Allergic to penicillin (hives). "
    "Takes sertraline 100 mg daily and prazosin 2 mg at night. "
    "Denies current suicidal ideation. Drinks 2-3 beers most nights."
)

CASES = [
    {
        "id": "keeps-allergy",
        "input": INTAKE,
        "checks": {"must_include": ["penicillin"]},
        "weight": 3,
    },
    {
        "id": "keeps-both-meds",
        "input": INTAKE,
        "checks": {"must_include": ["sertraline", "prazosin"]},
        "weight": 2,
    },
    {
        "id": "no-invented-meds",
        "input": INTAKE,
        "checks": {"must_not_include": ["trazodone", "quetiapine", "hydroxyzine"]},
        "weight": 3,
    },
    {
        "id": "keeps-alcohol-signal",
        "input": INTAKE,
        "checks": {"must_include": ["beer"]},
        "weight": 2,
    },
    {
        "id": "length-budget",
        "input": INTAKE,
        "checks": {"max_words": 60},
        "weight": 1,
    },
]


def good_model(prompt: str, case_input: str) -> str:
    """Terse, faithful summary — keeps every load-bearing fact."""
    return (
        "58yo veteran with PTSD/insomnia. Penicillin allergy (hives). "
        "Sertraline 100 mg daily, prazosin 2 mg qhs. No current SI. "
        "2-3 beers most nights."
    )


def fluent_but_wrong_model(prompt: str, case_input: str) -> str:
    """Reads beautifully; drops the allergy, invents a med, launders the
    alcohol history into vagueness. This is what 'looks fine' fails like."""
    return (
        "This 58-year-old veteran presents with PTSD and insomnia, currently "
        "managed with sertraline 100 mg daily and trazodone at bedtime. "
        "He denies suicidal ideation and reports occasional social drinking."
    )


def test_good_model_passes_gate():
    report = run_eval("summarize", CASES, good_model)
    assert report.score == 1.0
    assert report.gate(0.9)


def test_fluent_but_wrong_model_fails_gate():
    report = run_eval("summarize", CASES, fluent_but_wrong_model)
    assert not report.gate(0.9)
    failed_ids = {r.case_id for r in report.failed}
    # The rubric catches exactly the clinically dangerous failures:
    assert "keeps-allergy" in failed_ids       # dropped penicillin
    assert "no-invented-meds" in failed_ids    # hallucinated trazodone
    assert "keeps-alcohol-signal" in failed_ids  # laundered to "social drinking"


def test_weighted_score_reflects_severity():
    report = run_eval("summarize", CASES, fluent_but_wrong_model)
    # 4 of 5 cases fail (it also swapped prazosin for trazodone), carrying
    # 10 of 11 weight -> only the length check passes.
    assert report.score == pytest.approx(1 / 11)


def test_markdown_report_names_failures():
    report = run_eval("summarize", CASES, fluent_but_wrong_model)
    md = report.to_markdown()
    assert "keeps-allergy" in md and "FAIL" in md and "missing" in md


def test_valid_json_check_handles_fences():
    fenced = 'Here you go:\n```json\n{"risk": "low", "follow_up_days": 14}\n```'
    r = valid_json(fenced, required_keys=["risk", "follow_up_days"])
    assert r.passed
    assert not valid_json("not json at all").passed


def test_unknown_check_raises():
    with pytest.raises(KeyError):
        run_checks("output", {"vibes": True})


def test_load_cases_jsonl(tmp_path):
    p = tmp_path / "cases.jsonl"
    p.write_text(
        '# comment line\n'
        '{"id": "a", "input": "x", "checks": {"max_words": 5}}\n'
        '\n'
        '{"id": "b", "input": "y", "checks": {"must_include": ["z"]}, "weight": 2}\n'
    )
    cases = load_cases(p)
    assert [c["id"] for c in cases] == ["a", "b"]
    assert cases[1]["weight"] == 2


def test_empty_report_scores_zero():
    assert EvalReport([]).score == 0.0
