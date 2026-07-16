"""Degradation gate for the live eval runner — pure computation, no I/O.

evaluate_degradation() is the single source of truth for "is this eval run
healthy?" so it can be unit-tested offline (tests/test_run_evals_gate.py)
and reused by scripts/run_evals.py's main(). It depends only on evals.checks
(for CheckResult), never on scripts.run_evals, to avoid a circular import —
scripts/run_evals.py is the one that imports this module, not the reverse.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from evals.checks import CheckResult


class RunResultLike(Protocol):
    """Structural stand-in for scripts.run_evals.RunResult — outcome and
    checks are all evaluate_degradation needs. A Protocol lets this module
    stay independent of the scripts package (which imports this module)."""

    outcome: str
    checks: list[CheckResult]


def evaluate_degradation(results: Sequence[RunResultLike], fail_under: float | None) -> list[str]:
    """Return human-readable failure messages; an empty list means healthy.

    The gate is entirely opt-in: when fail_under is None (the flag's
    default, "off"), this always returns []. When a threshold is given, two
    independent conditions are both checked (never short-circuited, so a
    single run surfaces every problem at once):

      1. Overall contract-ok rate (ok + repaired) / total must be >=
         fail_under.
      2. Every quality check's pass-rate over contract-valid replies (ok +
         repaired only — "failed" runs carry no checks) must be exactly
         1.0: quality checks passing is the baseline, not a threshold to
         tune against fail_under.
    """
    if fail_under is None:
        return []

    failures: list[str] = []
    total = len(results)
    if total == 0:
        return failures

    ok_count = sum(1 for r in results if r.outcome in ("ok", "repaired"))
    ok_rate = ok_count / total
    if ok_rate < fail_under:
        failures.append(f"Eval degradation: ok-rate {ok_rate:.2f} < required {fail_under:.2f}")

    check_names = sorted({c.name for r in results for c in r.checks})
    for name in check_names:
        checked = [c for r in results for c in r.checks if c.name == name]
        passed = sum(1 for c in checked if c.passed)
        if checked and passed < len(checked):
            rate = passed / len(checked)
            failures.append(
                f"Eval degradation: check '{name}' pass-rate {rate:.2f} < 1.00 "
                f"({passed}/{len(checked)})"
            )
    return failures
