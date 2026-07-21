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


@dataclass
class EvalReport:
    results: list[CaseResult]

    @property
    def score(self) -> float:
        """Weighted pass rate, 0.0–1.0."""
        total = sum(r.weight for r in self.results)
        if total == 0:
            return 0.0
        return sum(r.weight for r in self.results if r.passed) / total

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
