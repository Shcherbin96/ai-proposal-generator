# Résumé descriptions — AI Proposal Generator

Two ready-to-paste variants. All claims are backed by the repository, its tests,
and CI.

---

## Short version (2–3 lines, for a "Projects" section)

> **AI Proposal Generator** — Python tool that turns a product list into a
> branded commercial-proposal PDF, cutting a ~3-hour manual task to ~2 minutes.
> A strict LLM/code boundary makes hallucinated numbers architecturally
> impossible (prices never reach the model; all arithmetic is computed in
> Python). 162 tests, ~98% coverage, cross-platform CI, Docker, and automated
> LLM evals. *Python, pydantic, OpenAI-compatible API, Jinja2, GitHub Actions,
> Docker.*

---

## Extended version (4–6 bullets)

**AI Proposal Generator** — automated LLM→PDF commercial-proposal generator
(personal project) · *Python, pydantic, OpenAI-compatible LLM API, Jinja2,
Docker, GitHub Actions*

- Automated a real business process end to end, cutting proposal preparation
  from **~3 hours of manual work to ~2 minutes**.
- Designed a strict **LLM/code boundary** enforced by `pydantic` on both sides
  of the model: prices never enter the prompt, the reply is rejected unless it
  covers every product exactly once in order, and **all financial data is
  computed deterministically in Python** — hallucinated numbers are impossible by
  construction.
- Built layered structured-output reliability — **JSON mode, a bounded
  content-repair loop, and typed errors with `sysexits` exit codes** — plus
  injection-safe rendering and verified PDF output.
- Wrote **162 offline tests (~98% coverage, strict mypy)** and cross-platform CI
  on **Ubuntu, macOS, and Windows**, with a Docker build and a coverage gate.
- Implemented an **automated LLM evaluation** pipeline: offline quality checks in
  CI, a committed live eval report, and a **weekly scheduled eval with a
  degradation gate that auto-opens an issue** on quality regression.
- Packaged as a reproducible **Docker image with bundled Chromium**, digest-
  pinned, and released as **v1.0.0**.

---

### Notes for tailoring

- For **AI Automation Specialist / AI Integration Engineer**: lead with the
  ~3h→~2min automation and the provider-agnostic OpenAI-compatible integration.
- For **AI Systems Builder / AI Implementation Engineer**: lead with the
  LLM/code boundary, the reliability layers, and the eval + CI discipline.
- Keep the phrase "hallucinated numbers are impossible by construction" — it is
  the strongest, most memorable, and fully true claim.
