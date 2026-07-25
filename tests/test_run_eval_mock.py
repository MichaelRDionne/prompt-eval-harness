"""Regression coverage for scripts/run_eval.py's deterministic mock path.

test_eval_gate.py proves the harness mechanism itself (evalharness.runner)
works end to end. This file proves the CLI script's own mock target and
scoring behave the way the module docstring and README claim: prompt-
sensitive, deterministic, and separating baseline from hardened by a real
margin. That claim is exactly what a local `--mock` run relies on when
ANTHROPIC_API_KEY is absent, so it deserves its own test rather than living
as an unverified assertion in prose.
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from evalharness.runner import load_cases  # noqa: E402

import run_eval  # noqa: E402

CASES = load_cases(run_eval.CASES_PATH)


def test_generic_suite_has_cases():
    # Guards the fixtures below against an accidentally-emptied suite file.
    assert len(CASES) >= 5


def test_mock_target_is_deterministic():
    case = CASES[0]
    out1 = run_eval.mock_target(run_eval.HARDENED_PROMPT, case["input"])
    out2 = run_eval.mock_target(run_eval.HARDENED_PROMPT, case["input"])
    assert out1 == out2


def test_mock_target_is_prompt_sensitive():
    """At least one case must produce different output text under the
    baseline vs. hardened prompt — otherwise the mock measures nothing and
    the README's 'illustrative delta' claim is false."""
    differs = any(
        run_eval.mock_target(run_eval.BASELINE_PROMPT, c["input"])
        != run_eval.mock_target(run_eval.HARDENED_PROMPT, c["input"])
        for c in CASES
    )
    assert differs


def test_mock_target_raises_on_unrecognized_input():
    # Every branch in mock_target ends in this raise; an unrecognized case
    # input should fail loud rather than silently return an empty string.
    import pytest

    with pytest.raises(ValueError):
        run_eval.mock_target(run_eval.HARDENED_PROMPT, "no case matches this text")


def test_hardened_mock_beats_baseline_mock():
    """The documented failure mode: baseline scores low, hardened scores
    high, on the same suite. Guards against a future edit accidentally
    making the mock's baseline as good as its hardened condition, which
    would make the demo dishonest."""
    baseline = run_eval.run_condition(run_eval.BASELINE_PROMPT, CASES, run_eval.mock_target, k=1)
    hardened = run_eval.run_condition(run_eval.HARDENED_PROMPT, CASES, run_eval.mock_target, k=1)
    assert hardened["score"] > baseline["score"]
    assert hardened["score"] >= run_eval.DEFAULT_GATE


def test_mock_baseline_fails_default_gate():
    """Mirrors the README's claim that the baseline mock is a
    fluent-but-wrong failure, not a near-miss."""
    baseline = run_eval.run_condition(run_eval.BASELINE_PROMPT, CASES, run_eval.mock_target, k=1)
    assert baseline["score"] < run_eval.DEFAULT_GATE


def test_render_scorecard_svg_is_well_formed():
    history = [
        {"date": "2026-01-01", "mode": "mock", "baseline_score": 0.30, "hardened_score": 0.85, "gate_pass": True},
        {"date": "2026-01-08", "mode": "live", "baseline_score": 0.80, "hardened_score": 0.92, "gate_pass": True},
    ]
    svg = run_eval.render_scorecard_svg(history)
    assert svg.startswith("<svg")
    assert svg.strip().endswith("</svg>")
    assert "GATE PASS" in svg
    assert "92%" in svg  # latest hardened score, rounded


def test_render_scorecard_svg_reflects_gate_fail():
    history = [
        {"date": "2026-01-01", "mode": "live", "baseline_score": 0.5, "hardened_score": 0.4, "gate_pass": False},
    ]
    svg = run_eval.render_scorecard_svg(history)
    assert "GATE FAIL" in svg


def test_render_scorecard_svg_handles_single_history_row():
    # Sparkline logic branches on len(live) == 0 / 1 / >=2; a single-row
    # history must not raise (regression guard for the "awaiting first live
    # run" / "1 live run logged" branches).
    history = [
        {"date": "2026-01-01", "mode": "live", "baseline_score": 0.5, "hardened_score": 0.6, "gate_pass": False},
    ]
    svg = run_eval.render_scorecard_svg(history)
    assert "1 live run logged" in svg
