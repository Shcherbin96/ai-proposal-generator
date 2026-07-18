# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-07-18

First stable release. The pipeline, its contracts, tests, CI, evals, and
container image are complete and verified end-to-end against a live model.
No behavioural changes are planned for the 1.x line beyond fixes.

### The core guarantee
- **The LLM writes prose; Python owns every number.** Prices never enter the
  prompt; the model's reply is rejected unless it covers every product exactly
  once, in order (index-based contract); the total is computed in Python from
  the validated input. Hallucinated figures are impossible by construction.

### Reliability
- Strict `pydantic` contracts on **both** LLM boundaries — the input YAML and
  the model's JSON reply — with readable, typed errors.
- Typed exceptions mapped to BSD `sysexits` codes (`65` input, `78` config,
  `69` LLM, `73` render), so a wrapping script can tell failure classes apart.
- Layered structured-output robustness: **JSON mode** (default on), a **bounded
  content-repair loop** that feeds the validation error back to the model, and
  the SDK's **transport retries** — three independent, separately-configured knobs.
- Prices parsed as `Decimal` with two-place precision; a `money` filter that
  guarantees displayed line items sum to the displayed total.
- Injection-safe rendering: Jinja2 `autoescape` + `StrictUndefined`.
- Verified output: a PDF is reported as success only after Chrome exits 0, the
  file exists, is non-empty, and starts with the `%PDF-` magic bytes.
- Per-call observability: one structured log line with model, prompt version,
  token counts, and latency; the API key is never logged or shown in `repr`.

### Testing & CI
- **162 offline tests** (no API key, no network) via a canned fixture and a
  `FakeProvider`; **~98% coverage** with a 94% gate on the Linux CI leg.
- `ruff` lint + format and **strict `mypy`** over `proposal_gen`, `scripts`, `evals`.
- Cross-platform CI: the full suite on **Ubuntu, macOS, and Windows**; a
  Docker build-only job; SHA-pinned actions; least-privilege permissions;
  Dependabot for `github-actions`, `uv`, and `docker`.

### AI evaluation
- **Offline** quality checks (`evals/checks.py`) run in CI: language match,
  length bounds, no invented numbers, no markdown artifacts.
- **Live** eval harness (`scripts/run_evals.py`) with a committed report
  (`docs/eval-report.md`): 30 calls, 26 first-reply contract-valid, 1 recovered
  by the repair loop, 3 truncated-JSON failures, and 27/27 on every quality check.
- **Scheduled** weekly workflow (`.github/workflows/evals.yml`) with a
  degradation gate (`evaluate_degradation`) that fails the run and auto-opens a
  GitHub issue if the contract-ok rate drops below 80% or any quality check
  regresses — continuous monitoring, not a one-off number.

### Packaging
- Reproducible **Docker image** (~1.3 GB) with bundled Chromium and vendored
  OFL fonts; runs offline, digest-pinned base + `uv`.
- Offline-reproducible example artifact (`scripts/make_example.py`) — regenerate
  the sample PDF and README screenshot with no API key.
- MIT licensed.

### Known limitations (unchanged, documented in the README)
- One branded A4 template; ruble currency and RU date format are template-level.
- Prose is validated structurally and against heuristics, **not** for
  persuasiveness — that still needs human judgment.
- Prompt injection is **bounded, not prevented**: a hostile input can influence
  the prose but not any number, the document structure, HTML, or secrets.
- Human review is expected before a proposal is sent to a client.

[1.0.0]: https://github.com/Shcherbin96/ai-proposal-generator/releases/tag/v1.0.0
