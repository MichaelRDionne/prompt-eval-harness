"""CI enforcement gate for the domain-neutral eval suite.

This is deliberately separate from scripts/run_eval.py's own deterministic
mock: that mock exists to *demonstrate* a fluent-but-wrong failure (see its
docstring), so it fails the gate on purpose. This test proves the harness
mechanism itself works end-to-end on examples/generic_eval.jsonl, using a
target that gets every case right, and asserts the gate passes at a sensible
threshold. That's the thing CI should actually enforce on every push.
"""

from pathlib import Path

from evalharness.runner import load_cases, run_eval

CASES_PATH = Path(__file__).resolve().parent.parent / "examples" / "generic_eval.jsonl"

GATE_THRESHOLD = 0.9


def compliant_target(prompt: str, case_input: str) -> str:
    """A target that satisfies every check in examples/generic_eval.jsonl —
    the fully-correct counterpart to run_eval.py's fluent-but-wrong mock. Unlike
    the mock it is prompt-agnostic: it always returns the right answer, so the
    gate passes end to end on every case."""
    text = case_input

    if "BREAKING CHANGE" in text:
        return (
            "Release 2.4.0 adds dark mode and a 15% faster startup, fixes a "
            "Windows multi-monitor crash, and ships a breaking change: "
            "`config.timeout` now expects milliseconds instead of seconds."
        )

    if "parseLegacyConfig" in text:
        return (
            "`parseLegacyConfig()` is deprecated in favor of `parseConfig()` "
            "ahead of v3.0; YAML config file support was also added."
        )

    if "model-B sensor" in text:
        return '{"item": "model-B sensor", "quantity": 3}'

    if "ERR_429" in text:
        return "Payments returning ERR_429 since 14:02 UTC; on-call investigating."

    if "37.4%" in text:
        return "The caching change cut p95 latency by 37.4%, with error rates unchanged."

    if "Vendor note to reviewer" in text:
        return (
            "The subscription is a 12-month term that auto-renews unless "
            "cancelled 30 days before the end date, with fees invoiced "
            "quarterly on net 30 terms and four-hour support for critical issues."
        )

    if "Checkout Service Degradation" in text:
        return "The checkout outage lasted 43 minutes, from the first errors to full recovery."

    if "move forward on four fronts" in text:
        return (
            "Decisions: complete the database migration to the new cluster, "
            "update the API docs for the new endpoints, renew the TLS "
            "certificate before expiry, and archive old audit logs to cold "
            "storage; owners assigned, reviewed next sprint."
        )

    if "internal platform migration" in text:
        return (
            "The note does not state an external launch date; it covers "
            "technical readiness and downstream coordination only."
        )

    if "Northwind Logistics" in text:
        return '{"vendor": "Northwind Logistics", "effective_date": "2026-03-01", "renewal_date": null}'

    raise ValueError(f"compliant_target has no branch for input: {text!r}")


def test_generic_suite_loads():
    cases = load_cases(CASES_PATH)
    assert len(cases) >= 5


def test_compliant_target_passes_gate():
    cases = load_cases(CASES_PATH)
    report = run_eval("system prompt", cases, compliant_target)
    assert not report.failed, [
        (r.case_id, [c.detail for c in r.checks if not c.passed]) for r in report.failed
    ]
    assert report.gate(GATE_THRESHOLD)
