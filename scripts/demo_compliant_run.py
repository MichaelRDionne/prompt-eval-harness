#!/usr/bin/env python3
"""Demo-only helper (used by assets/demo.tape): run the generic_eval suite
against a fully compliant mock target, so the recording can show what a
passing gate looks like right after scripts/run_eval.py's deterministic
fluent-but-wrong path shows a failing one. Not part of CI — tests/test_eval_gate.py
is the actual enforcement, this just re-prints the same result for the recording.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from evalharness.runner import load_cases, run_eval  # noqa: E402
from tests.test_eval_gate import compliant_target  # noqa: E402

CASES_PATH = REPO_ROOT / "examples" / "generic_eval.jsonl"

if __name__ == "__main__":
    report = run_eval("system prompt", load_cases(CASES_PATH), compliant_target)
    print(report.to_markdown())
    print()
    print(f"Gate(0.9): {'PASS' if report.gate(0.9) else 'FAIL'}")
