"""Offline coverage for evals/gate.py — no network, runs in CI.

evaluate_degradation() is the pure computation behind scripts/run_evals.py's
--fail-under-ok-rate flag; these tests build fake per-run results directly
(mirroring the shape of scripts.run_evals.RunResult) rather than importing
that module, keeping this a unit test of evals.gate alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from evals.checks import CheckResult
from evals.gate import evaluate_degradation


@dataclass
class FakeResult:
    """Structurally matches evals.gate.RunResultLike."""

    outcome: str
    checks: list[CheckResult] = field(default_factory=list)


def _passed(*names: str) -> list[CheckResult]:
    return [CheckResult(name, True, "ok") for name in names]


def _with_one_failed(failed_name: str, all_names: tuple[str, ...]) -> list[CheckResult]:
    return [CheckResult(name, name != failed_name, "detail") for name in all_names]


CHECK_NAMES = ("language_match", "length_bounds", "no_invented_numbers", "no_markdown_artifacts")


def test_healthy_grid_returns_no_failures():
    results = [FakeResult("ok", _passed(*CHECK_NAMES)) for _ in range(8)] + [
        FakeResult("repaired", _passed(*CHECK_NAMES)) for _ in range(2)
    ]
    assert evaluate_degradation(results, fail_under=0.8) == []


def test_low_ok_rate_reports_message_with_rate_and_threshold():
    # 5 ok, 5 failed -> ok-rate 0.50, below the 0.80 floor.
    results = [FakeResult("ok", _passed(*CHECK_NAMES)) for _ in range(5)] + [
        FakeResult("failed") for _ in range(5)
    ]
    messages = evaluate_degradation(results, fail_under=0.8)
    assert any("ok-rate 0.50 < required 0.80" in m for m in messages)


def test_one_check_below_full_pass_rate_names_the_check():
    # 4 contract-valid runs; one of them fails the no_markdown_artifacts check.
    results = [
        FakeResult("ok", _passed(*CHECK_NAMES)),
        FakeResult("ok", _passed(*CHECK_NAMES)),
        FakeResult("repaired", _passed(*CHECK_NAMES)),
        FakeResult("ok", _with_one_failed("no_markdown_artifacts", CHECK_NAMES)),
    ]
    messages = evaluate_degradation(results, fail_under=0.8)
    assert any("no_markdown_artifacts" in m for m in messages)
    assert not any("language_match" in m for m in messages)


def test_gate_off_when_fail_under_is_none():
    # Even a maximally unhealthy grid produces no failures when the flag
    # (default None) was never passed — the gate is opt-in.
    results = [FakeResult("failed") for _ in range(10)]
    assert evaluate_degradation(results, fail_under=None) == []


def test_healthy_grid_with_gate_off_is_also_empty():
    results = [FakeResult("ok", _passed(*CHECK_NAMES)) for _ in range(3)]
    assert evaluate_degradation(results, fail_under=None) == []


def test_both_conditions_can_fail_at_once():
    results = [
        FakeResult("ok", _with_one_failed("length_bounds", CHECK_NAMES)),
    ] + [FakeResult("failed") for _ in range(4)]
    messages = evaluate_degradation(results, fail_under=0.8)
    assert any("ok-rate" in m for m in messages)
    assert any("length_bounds" in m for m in messages)
    assert len(messages) == 2


def test_empty_results_is_healthy():
    assert evaluate_degradation([], fail_under=0.8) == []
