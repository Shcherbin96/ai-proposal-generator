# Portfolio case — AI Proposal Generator

A written case study for a technical recruiter or hiring manager. It explains
what the project is, the engineering decisions behind it, and the measurable
result — without requiring you to read the code. Every technical claim here is
backed by code, a test, or CI; nothing is inflated.

Repository: <https://github.com/Shcherbin96/ai-proposal-generator>

---

## 1. Project overview

A command-line tool and Docker service that turns a plain YAML product list into
a branded, client-ready commercial-proposal PDF. A language model writes the
prose; Python computes and owns every number. The whole project exists to make
one guarantee real: **the model cannot get a price, a total, or a product wrong.**

The codebase is deliberately small — about 560 lines of production code across
seven modules — with more test code than production code. The value is not
volume; it is the production-grade shell around a single LLM call.

## 2. Business problem

A small interior-supply business prepares a commercial proposal for every
customer inquiry: a tailored intro, a benefit sentence per product, prices, a
total, and a closing. Done by hand in a word processor, one proposal took about
**three hours** — mostly formatting and rewriting similar sentences. The tool
produces the same document in about **two minutes**, and because the numbers are
computed by code rather than written by the model, the document is safe to send
without re-checking the arithmetic.

## 3. My role

Sole engineer. I designed the architecture, wrote all production and test code,
set up the CI/CD and evaluation pipelines, containerized it, and wrote the
documentation. The work was done as a series of small, reviewed pull requests
with green CI at each step, culminating in a tagged `v1.0.0` release.

## 4. Architecture

A four-stage pipeline, each stage logged and each failure typed:

```
products.yaml
   → validate input        (pydantic, Decimal prices)
   → build prompt          (product names only — no prices)
   → LLM                   (any OpenAI-compatible endpoint; JSON mode)
   → validate reply        (every index 0..N-1 exactly once, in order)
   → merge prose + prices  (total computed in Python)
   → render HTML           (Jinja2, autoescape, StrictUndefined)
   → headless Chrome       (print to PDF)
   → verify output         (non-empty, %PDF- magic bytes)
   → proposal.pdf
```

The LLM is behind a small `Protocol` interface, so any OpenAI-compatible
provider (Gemini, OpenAI, a local model) or a test double plugs in without
touching business logic.

## 5. LLM boundary and deterministic business logic

This is the central design decision. The boundary is enforced in both
directions by strict `pydantic` models:

- **Into the model** goes the client name, project name, and a numbered list of
  product *names* — never prices. A test (`test_prompt_contains_names_but_never_prices`)
  asserts that no input price ever appears in the prompt.
- **Out of the model** must come strict JSON with one description per product,
  each carrying an **explicit index**. The reply is rejected unless the indices
  are exactly `0..N-1`, in order — no missing products, no duplicates, no
  reordering. This is why a slightly-wrong reply fails loudly instead of pairing
  the wrong description with the wrong price.
- **The numbers** never round-trip through the model. Prices are parsed as
  `Decimal` with two-place precision; the total is summed in Python; a `money`
  filter guarantees the displayed line items always sum to the displayed total.

The result: the model can write a weak sentence, but it cannot corrupt a price,
drop a product, or invent a discount. Hallucinated figures are impossible by
construction, not by prompt-engineering hope.

## 6. Reliability and error handling

- **Typed exceptions → exit codes.** Four failure classes map to BSD `sysexits`
  codes (65 input, 78 config, 69 LLM, 73 render), so automation around the tool
  can distinguish bad input from bad config from a downed provider from a render
  failure without parsing stderr.
- **Layered structured-output robustness.** JSON mode reduces malformed replies;
  a bounded content-repair loop feeds the validation error back to the model
  once before failing; the SDK's transport retries handle network flakiness.
  Three independent, separately-configured knobs — a deliberate separation.
- **Injection-safe rendering.** Jinja2 runs with `autoescape=True` and
  `StrictUndefined`; both the injection path and the missing-variable path have
  tests.
- **Verified output.** A PDF is reported as success only after Chrome exits 0
  *and* the file exists, is non-empty, and starts with the `%PDF-` magic bytes —
  "Chrome exited 0 but produced no PDF" is a real, tested failure mode.
- **Secret hygiene.** The API key is excluded from `repr` and never logged; a
  test asserts it.
- **Philosophy.** Expected failures are caught, classified, and explained;
  unexpected ones are allowed to traceback — a bug should look like a bug, not be
  laundered into a polite message.

## 7. Testing strategy

- **162 tests, ~98% coverage**, all offline: no API key, no network. The LLM is
  replaced by a `FakeProvider` that replays a canned fixture and records the
  prompts it receives, so tests can assert on prompt contents (for example, that
  prices never appear).
- Coverage is enforced with a **94% gate on the Linux CI leg**; the small
  uncovered remainder is structural (per-OS branches in Chrome discovery, and a
  subprocess-only entry point), not neglect.
- Tests that need a real Chrome binary skip gracefully when it is absent, but CI
  runs a loud assertion that Chrome *is* present on every runner — so the one
  path that can only be tested with a real browser can never silently vanish
  from coverage.

## 8. LLM evaluation strategy

Tests prove the plumbing; evals prove the product.

- **Offline checks** (`evals/checks.py`, run in CI): four pure functions over
  `(input, reply)` — language match, per-section length bounds, no invented
  numbers in the prose, no markdown artifacts. Each has a passing fixture and a
  hand-crafted failing case, so a check that silently stopped working would break
  the build.
- **Live report** (`docs/eval-report.md`): 30 real calls across five golden
  inputs and two repair configurations — **26 contract-valid on the first reply,
  1 recovered by the repair loop, 3 truncated-JSON failures, 27/27 on every
  quality check.**
- **Scheduled monitoring** (`evals.yml`): a weekly workflow with a **degradation
  gate** (`evaluate_degradation`, unit-tested) that fails the run and
  **auto-opens a GitHub issue** if the contract-ok rate drops below 80% or any
  quality check regresses. Continuous quality monitoring, not a one-off number.

## 9. CI/CD and deployment

- **CI** (`ci.yml`): ruff lint + format check and strict `mypy`
  (`proposal_gen`, `scripts`, `evals`) on Linux; the full test suite on
  **Ubuntu, macOS, and Windows**; a coverage gate on the Linux leg; and a Docker
  build-only job. Least-privilege permissions, per-ref concurrency cancellation,
  job timeouts, actions pinned by commit SHA, and Dependabot for GitHub Actions,
  `uv`, and Docker.
- **Container** (`Dockerfile`): a reproducible ~1.3 GB image with bundled
  Chromium and vendored OFL fonts, digest-pinned base + `uv`. It runs fully
  offline once built; the vector of secrets is env-vars only, and `.env` is
  excluded from the image.
- **Release**: tagged `v1.0.0` with a `CHANGELOG.md`.

## 10. Measured result

- **Time:** ~3 hours of manual work → ~2 minutes per proposal.
- **Correctness:** 0 hallucinated numbers possible by architecture; on the live
  eval, 27/27 on every quality check across all contract-valid replies.
- **Quality bar:** 162 tests, ~98% coverage, strict typing, three operating
  systems, a live eval report, and automated weekly monitoring.

## 11. Engineering trade-offs

- **Headless Chrome over a pure-Python PDF library.** The template uses real web
  fonts and modern CSS; Chrome renders it exactly as a browser would with zero
  native Python dependencies. The cost — an external binary — is owned openly and
  solved for reproducibility with the Docker image.
- **No `max_tokens` cap.** A low cap would truncate JSON mid-object and
  manufacture exactly the contract failure the repair loop exists to catch. The
  trade is a bounded cost for avoiding a self-inflicted correctness bug.
- **Fail loudly, not silently.** Bad LLM JSON fails with a clean exit code rather
  than being patched over; the repair loop gets one bounded attempt, then stops.
- **A `Protocol`, not a provider framework.** One structural interface and one
  implementation — right-sized abstraction for one production provider and one
  test double.

## 12. Limitations

- One branded A4 template; ruble currency and RU date format are template-level.
- Prose is validated structurally and against heuristics — **not** for
  persuasiveness. Tone and factual aptness still need human judgment or an LLM
  judge.
- Prompt injection is **bounded, not prevented**: a hostile input can influence
  the prose but not any number, the document structure, HTML, or a secret.
- Human review is expected before a proposal is sent to a client.

## 13. Future improvements

- Multiple templates / themes and locale-aware currency and dates.
- An LLM-as-judge layer for persuasiveness, gated behind the existing eval
  harness so it does not become an unmonitored claim.
- A retrieval step to pull real product specs into the prompt (still numbers-in-
  Python).
- Additional document types (invoices, estimates) sharing the same
  prose-from-the-model, numbers-from-the-data architecture.
