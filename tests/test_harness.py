"""The demo IS the test suite: two mock 'models' answer the same synthetic
incident-summary task. Both outputs read fluently. One fails the eval.

That is the whole argument for evaluation-first prompt work — eyeballing
cannot tell these apart reliably, and a rubric can.
"""

import pytest

from evalharness.checks import run_checks, valid_json
from evalharness.runner import EvalReport, load_cases, run_eval

# Synthetic incident report — invented service, invented content.
INCIDENT = (
    "Payment API returned ERR_429 rate-limit errors intermittently starting "
    "14:02 UTC. Deploy v2.4.1 introduced a stale feature-flag bug; on-call "
    "rolled back to v2.3.9. Checkout errors affected roughly 6% of EU "
    "traffic for 40 minutes before mitigation."
)

CASES = [
    {
        "id": "keeps-error-code",
        "input": INCIDENT,
        "checks": {"must_include": ["ERR_429"]},
        "weight": 3,
    },
    {
        "id": "keeps-both-versions",
        "input": INCIDENT,
        "checks": {"must_include": ["v2.4.1", "v2.3.9"]},
        "weight": 2,
    },
    {
        "id": "no-invented-causes",
        "input": INCIDENT,
        "checks": {"must_not_include": ["memory leak", "database outage", "DNS failure"]},
        "weight": 3,
    },
    {
        "id": "keeps-impact-signal",
        "input": INCIDENT,
        "checks": {"must_include": ["6%"]},
        "weight": 2,
    },
    {
        "id": "length-budget",
        "input": INCIDENT,
        "checks": {"max_words": 60},
        "weight": 1,
    },
]


def good_model(prompt: str, case_input: str) -> str:
    """Terse, faithful summary — keeps every load-bearing fact."""
    return (
        "ERR_429 rate-limit errors from 14:02 UTC. Deploy v2.4.1's stale "
        "feature flag caused it; on-call rolled back to v2.3.9. ~6% of EU "
        "checkout traffic affected for 40 minutes."
    )


def fluent_but_wrong_model(prompt: str, case_input: str) -> str:
    """Reads beautifully; drops the error code, invents a root cause, and
    launders the impact figure into vagueness. This is what 'looks fine'
    fails like."""
    return (
        "The payment service experienced a brief spike in failed "
        "transactions this afternoon, traced to a memory leak introduced in "
        "the latest deploy. Engineers redeployed a fix and confirmed the "
        "issue affected only a small number of customers before resolution."
    )


def test_good_model_passes_gate():
    report = run_eval("summarize", CASES, good_model)
    assert report.score == 1.0
    assert report.gate(0.9)


def test_fluent_but_wrong_model_fails_gate():
    report = run_eval("summarize", CASES, fluent_but_wrong_model)
    assert not report.gate(0.9)
    failed_ids = {r.case_id for r in report.failed}
    # The rubric catches exactly the operationally dangerous failures:
    assert "keeps-error-code" in failed_ids     # dropped ERR_429
    assert "no-invented-causes" in failed_ids   # hallucinated "memory leak"
    assert "keeps-impact-signal" in failed_ids  # laundered to "a small number"


def test_weighted_score_reflects_severity():
    report = run_eval("summarize", CASES, fluent_but_wrong_model)
    # 4 of 5 cases fail (it also dropped both version numbers), carrying
    # 10 of 11 weight -> only the length check passes.
    assert report.score == pytest.approx(1 / 11)


def test_markdown_report_names_failures():
    report = run_eval("summarize", CASES, fluent_but_wrong_model)
    md = report.to_markdown()
    assert "keeps-error-code" in md and "FAIL" in md and "missing" in md


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
