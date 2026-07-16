"""Live eval runner: calls the REAL provider against evals/golden/*.yaml and
scores replies with evals/checks.py. This is a standalone script, never a
test — CI runs bare `pytest` with no markers and no API key, and this file
costs money and is nondeterministic by nature.

Usage:
    uv run python scripts/run_evals.py --reps 3
    uv run python scripts/run_evals.py --reps 3 --max-repairs 0 1 --output docs/eval-report.md

Passing two values to --max-repairs runs both configs and renders one
combined report (see docs/eval-report.md for the committed example).
`--help` works without an API key; an actual run needs LLM_API_KEY in .env.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.checks import CheckResult, run_all_checks  # noqa: E402
from evals.gate import evaluate_degradation  # noqa: E402
from proposal_gen import config  # noqa: E402
from proposal_gen.errors import ConfigError, InputError, LLMError  # noqa: E402
from proposal_gen.llm import (  # noqa: E402
    LLMProvider,
    OpenAICompatProvider,
    build_prompt,
    request_content,
)
from proposal_gen.models import ProposalInput, load_input  # noqa: E402

GOLDEN_DIR = ROOT / "evals" / "golden"


class _CountingProvider:
    """Wraps the real provider; counting calls tells "ok" (1 call) apart from
    "repaired" (2+ calls) — request_content itself doesn't report this."""

    def __init__(self, inner: LLMProvider) -> None:
        self._inner = inner
        self.calls = 0

    def complete(self, prompt: str) -> str:
        self.calls += 1
        return self._inner.complete(prompt)


@dataclass
class RunResult:
    golden_file: str
    outcome: str  # "ok" | "repaired" | "failed"
    latency_s: float
    checks: list[CheckResult] = field(default_factory=list)
    error: str | None = None


def run_one(
    data: ProposalInput, provider: LLMProvider, max_repairs: int, golden_name: str
) -> RunResult:
    # Mirror the pipeline's seller resolution (generate.py): a per-document
    # seller in the YAML overrides the config default.
    seller = data.seller.model_dump() if data.seller is not None else config.SELLER
    prompt = build_prompt(data, seller["name"], seller["tagline"])
    counting = _CountingProvider(provider)
    start = time.perf_counter()
    try:
        content = request_content(
            counting, prompt, expected_count=len(data.products), max_repairs=max_repairs
        )
    except LLMError as exc:
        # Transport failures and repair-budget exhaustion both surface as
        # LLMError here; either way this run is a contract failure, not a
        # crash — the caller keeps going to the next rep/file.
        return RunResult(golden_name, "failed", time.perf_counter() - start, error=str(exc))
    outcome = "ok" if counting.calls == 1 else "repaired"
    checks = run_all_checks(data, content)
    return RunResult(golden_name, outcome, time.perf_counter() - start, checks)


def _outcome_counts(results: list[RunResult]) -> tuple[int, int, int]:
    ok = sum(1 for r in results if r.outcome == "ok")
    repaired = sum(1 for r in results if r.outcome == "repaired")
    failed = sum(1 for r in results if r.outcome == "failed")
    return ok, repaired, failed


def _check_pass_table(results: list[RunResult], check_names: list[str]) -> list[str]:
    lines = ["| Check | Pass rate |", "|---|---|"]
    for name in check_names:
        total = sum(1 for r in results for c in r.checks if c.name == name)
        passed = sum(1 for r in results for c in r.checks if c.name == name and c.passed)
        lines.append(f"| {name} | {f'{passed}/{total}' if total else 'n/a'} |")
    return lines


def render_report(
    all_results: dict[int, list[RunResult]],
    *,
    model: str,
    base_url: str,
    temperature: float,
    json_mode: bool,
    reps: int,
    note: str | None = None,
) -> str:
    check_names = sorted(
        {c.name for results in all_results.values() for r in results for c in r.checks}
    )
    lines = [
        "# Live Eval Report",
        "",
        f"- Date: {date.today().isoformat()}",
        f"- Model: {model}",
        f"- Endpoint: {base_url}",
        f"- Temperature: {temperature}",
        f"- JSON mode: {json_mode}",
        f"- Reps per golden file: {reps}",
        f"- Max-repairs configs in this report: {', '.join(str(mr) for mr in all_results)}",
        "",
    ]
    if note:
        lines.extend([f"> {note}", ""])
    for max_repairs, results in all_results.items():
        lines.append(f"## max_repairs = {max_repairs}")
        lines.append("")
        by_file: dict[str, list[RunResult]] = {}
        for r in results:
            by_file.setdefault(r.golden_file, []).append(r)
        for name, runs in by_file.items():
            ok, repaired, failed = _outcome_counts(runs)
            avg_latency = sum(r.latency_s for r in runs) / len(runs)
            lines.append(f"### {name}")
            lines.append("")
            lines.append(
                f"Runs: {len(runs)} — ok: {ok}, repaired: {repaired}, failed: {failed} "
                f"(avg latency {avg_latency:.2f}s)"
            )
            lines.append("")
            lines.extend(_check_pass_table(runs, check_names))
            lines.append("")
            failures = [c for r in runs for c in r.checks if not c.passed]
            if failures:
                lines.append("Failure details:")
                lines.extend(f"- **{c.name}**: {c.detail}" for c in failures)
                lines.append("")
        ok, repaired, failed = _outcome_counts(results)
        lines.append(
            f"**Subtotal (max_repairs={max_repairs})**: {len(results)} runs — "
            f"ok {ok}, repaired {repaired}, failed {failed}"
        )
        lines.append("")

    all_flat = [r for results in all_results.values() for r in results]
    ok, repaired, failed = _outcome_counts(all_flat)
    lines.append("## Totals (all configs combined)")
    lines.append("")
    lines.append(f"- Total runs: {len(all_flat)}")
    lines.append(f"- Contract ok: {ok}")
    lines.append(f"- Contract repaired: {repaired}")
    lines.append(f"- Contract failed: {failed}")
    lines.extend(
        f"- {name}: "
        f"{sum(1 for r in all_flat for c in r.checks if c.name == name and c.passed)}/"
        f"{sum(1 for r in all_flat for c in r.checks if c.name == name)} passed"
        for name in check_names
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run live evals against evals/golden/*.yaml.")
    parser.add_argument(
        "--reps", type=int, default=3, help="repetitions per golden file (default 3)"
    )
    parser.add_argument(
        "--max-repairs",
        type=int,
        nargs="*",
        default=None,
        metavar="N",
        help="one or more max_repairs values (default: LLM_MAX_REPAIRS/Settings); "
        "pass two, e.g. --max-repairs 0 1, to compare configs in one report",
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="write markdown report here (default: stdout)"
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="seconds to sleep between live calls (rate-limit mitigation)",
    )
    parser.add_argument(
        "--note",
        default=None,
        help="free-text operational note included in the report header",
    )
    parser.add_argument(
        "--fail-under-ok-rate",
        type=float,
        default=None,
        metavar="FLOAT",
        help=f"degradation gate (default: off). If set, fail (exit {InputError.exit_code}) "
        "when the overall contract-ok rate (ok + repaired) / total across all configs is "
        "below this, or when any quality check's pass-rate over contract-valid replies is "
        "below 1.0",
    )
    args = parser.parse_args(argv)

    try:
        settings = config.load_settings()
    except ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return exc.exit_code
    max_repairs_values = (
        args.max_repairs if args.max_repairs is not None else [settings.max_repairs]
    )
    provider = OpenAICompatProvider(settings)
    golden_files = sorted(GOLDEN_DIR.glob("*.yaml"))

    all_results: dict[int, list[RunResult]] = {}
    consecutive_failures = 0
    for max_repairs in max_repairs_values:
        results: list[RunResult] = []
        for golden_file in golden_files:
            data = load_input(golden_file)
            for _ in range(args.reps):
                result = run_one(data, provider, max_repairs, golden_file.name)
                results.append(result)
                print(
                    f"{golden_file.name} (max_repairs={max_repairs}): {result.outcome} "
                    f"in {result.latency_s:.1f}s",
                    file=sys.stderr,
                )
                # Circuit breaker: a dead endpoint or exhausted quota fails
                # every call — stop burning money instead of finishing the grid.
                consecutive_failures = consecutive_failures + 1 if result.outcome == "failed" else 0
                if consecutive_failures >= 3:
                    print(
                        f"Aborting: 3 consecutive failures, last error: {result.error}",
                        file=sys.stderr,
                    )
                    # EX_UNAVAILABLE, same as LLMError's exit code in the CLI:
                    # a dead endpoint / exhausted quota is a provider failure.
                    return LLMError.exit_code
                if args.sleep:
                    time.sleep(args.sleep)
        all_results[max_repairs] = results

    report = render_report(
        all_results,
        model=settings.model,
        base_url=settings.base_url,
        temperature=settings.temperature,
        json_mode=settings.json_mode,
        reps=args.reps,
        note=args.note,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(report)

    # Gate check runs after the report is written, so a degraded run still
    # leaves a reviewable artifact (e.g. for CI's upload-artifact: if:
    # always() step) even when this exits non-zero.
    all_flat = [r for results in all_results.values() for r in results]
    degradations = evaluate_degradation(all_flat, args.fail_under_ok_rate)
    if degradations:
        for message in degradations:
            print(message, file=sys.stderr)
        return InputError.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
