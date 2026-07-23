"""Case runner and scoring.

A "target" is any callable (prompt_template, case_input) -> output string.
That indirection is the point: the same cases score a raw model call, a
prompt v2, a RAG chain, or a mock — so prompt changes get regression-tested
like code changes.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .checks import CheckResult, run_checks

Target = Callable[[str, str], str]


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    weight: float
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def case_score(self) -> float:
        """Partial credit: the fraction of this case's checks that passed,
        0.0–1.0. A case with 3 checks where 2 pass scores 2/3, not 0 — so the
        aggregate degrades gracefully instead of flipping all-or-nothing on a
        single miss. `passed` (all checks green) is kept separately for the
        'cases passed' count."""
        if not self.checks:
            return 0.0
        return sum(1 for c in self.checks if c.passed) / len(self.checks)


@dataclass
class EvalReport:
    results: list[CaseResult]

    @property
    def score(self) -> float:
        """Weight-averaged partial-credit score, 0.0–1.0: each case contributes
        its fraction of checks passed, scaled by its weight (severity)."""
        total = sum(r.weight for r in self.results)
        if total == 0:
            return 0.0
        return sum(r.weight * r.case_score for r in self.results) / total

    @property
    def failed(self) -> list[CaseResult]:
        return [r for r in self.results if not r.passed]

    def gate(self, threshold: float) -> bool:
        """CI gate: True when the weighted score meets the threshold."""
        return self.score >= threshold

    def to_markdown(self) -> str:
        lines = [
            f"# Eval report — score {self.score:.0%} "
            f"({len(self.results) - len(self.failed)}/{len(self.results)} cases)",
            "",
            "| case | result | detail |",
            "|---|---|---|",
        ]
        for r in self.results:
            status = "PASS" if r.passed else "**FAIL**"
            detail = "; ".join(
                f"{c.name}: {c.detail}" for c in r.checks if not c.passed
            ) or "-"
            lines.append(f"| {r.case_id} | {status} | {detail} |")
        return "\n".join(lines)


def load_cases(path: str | Path) -> list[dict]:
    """Load cases from a JSONL file: one case object per line.

    Case format:
        {"id": "...", "input": "...", "checks": {...}, "weight": 2}
    """
    cases = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            cases.append(json.loads(line))
    return cases


def run_eval(prompt: str, cases: list[dict], target: Target) -> EvalReport:
    results = []
    for case in cases:
        output = target(prompt, case["input"])
        checks = run_checks(output, case["checks"])
        results.append(
            CaseResult(
                case_id=case["id"],
                passed=all(c.passed for c in checks),
                weight=float(case.get("weight", 1.0)),
                checks=checks,
            )
        )
    return EvalReport(results)
