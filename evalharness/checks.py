"""Deterministic output checks — the core of the harness.

Every check is pure and reproducible: no API keys, no LLM judges, no vibes.
LLM-graded rubrics are a legitimate extension, but the deterministic layer
comes first because it is the layer that catches regressions for free on
every prompt edit.
"""

import json
import re
from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def must_include(output: str, terms: list[str], case_sensitive: bool = False) -> CheckResult:
    """Every term must appear. The workhorse check: did the output keep the
    facts that matter (the allergy, the dose, the safety flag)?"""
    haystack = output if case_sensitive else output.lower()
    missing = [t for t in terms if (t if case_sensitive else t.lower()) not in haystack]
    return CheckResult(
        "must_include",
        not missing,
        "all present" if not missing else f"missing: {missing}",
    )


def must_not_include(output: str, terms: list[str], case_sensitive: bool = False) -> CheckResult:
    """No term may appear. Catches hallucinated content and leaked instructions."""
    haystack = output if case_sensitive else output.lower()
    found = [t for t in terms if (t if case_sensitive else t.lower()) in haystack]
    return CheckResult(
        "must_not_include",
        not found,
        "none present" if not found else f"forbidden content found: {found}",
    )


def must_match(output: str, pattern: str) -> CheckResult:
    """Regex must match somewhere in the output (format contracts)."""
    ok = re.search(pattern, output) is not None
    return CheckResult("must_match", ok, f"pattern {pattern!r} {'matched' if ok else 'not found'}")


def max_words(output: str, limit: int) -> CheckResult:
    """Length budget. Verbosity is a regression too."""
    n = len(output.split())
    return CheckResult("max_words", n <= limit, f"{n} words (limit {limit})")


def valid_json(output: str, required_keys: list[str] | None = None) -> CheckResult:
    """Output must parse as JSON, optionally with required top-level keys.
    Tolerates a fenced ```json block, since models love those."""
    text = output.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        return CheckResult("valid_json", False, f"parse error: {exc}")
    if required_keys:
        missing = [k for k in required_keys if k not in obj]
        if missing:
            return CheckResult("valid_json", False, f"missing keys: {missing}")
    return CheckResult("valid_json", True, "parsed")


CHECKS = {
    "must_include": must_include,
    "must_not_include": must_not_include,
    "must_match": must_match,
    "max_words": max_words,
    "valid_json": valid_json,
}


def run_checks(output: str, spec: dict) -> list[CheckResult]:
    """Run every check named in a case's `checks` spec against an output.

    Spec format (one key per check, value = that check's argument):
        {"must_include": ["penicillin"], "max_words": 120}
    """
    results = []
    for name, arg in spec.items():
        if name not in CHECKS:
            raise KeyError(f"unknown check: {name}")
        fn = CHECKS[name]
        if isinstance(arg, dict):
            results.append(fn(output, **arg))
        elif isinstance(arg, list):
            results.append(fn(output, arg))
        else:
            results.append(fn(output, arg))
    return results
