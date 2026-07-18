# Demo script — AI Proposal Generator (5–7 minutes)

A presenter-facing walkthrough for a live demo or a screen recording. Timings
are guidance, not a stopwatch. Everything here runs without editing code and
without improvising — the commands and numbers are the ones in the repo.

> Setup before you start: have the repo open, a terminal in the project root,
> and `output/proposal.pdf` pre-generated (or generate it live in step 4). A
> valid `.env` with `LLM_API_KEY` is only needed for the live run in step 4;
> everything else works offline.

---

## 0. One-sentence framing (15 s)

> "This turns a plain product list into a client-ready commercial-proposal PDF.
> The interesting part isn't the PDF — it's the guarantee that the language
> model can never get a number wrong."

---

## 1. The business problem (45 s)

Say:
> "A small interior-supply business writes a commercial proposal for every
> inquiry — an intro tailored to the client, a benefit line per product, prices,
> a total, a closing. By hand in a word processor that's about **three hours**,
> mostly formatting and rewriting the same kinds of sentences."

> "This produces the same document in about **two minutes**: edit the list, run
> one command, send the PDF."

---

## 2. The input (30 s)

Open `data/products.yaml`. Point at each part:
> "The whole input is this file — the **client**, the **project**, the
> **products with prices**, and the **seller** branding (optional, falls back to
> config). That's it."

```yaml
client: "ООО «Ромашка»"
project: "Ванная комната, 6 м²"
products:
  - name: "Смеситель для раковины Grohe Eurosmart"
    price: 8900
  - name: "Унитаз подвесной Roca Gap с инсталляцией"
    price: 21500
```

---

## 3. The core idea — LLM writes prose, code owns numbers (60 s)

This is the heart of the demo. Say:
> "The one rule the whole project is built around: **the language model writes
> only text. Python owns the products, the prices, the total, and the document
> structure.**"

Show it concretely — open `proposal_gen/llm.py`, point at `build_prompt`:
> "Notice what goes *into* the model: the client name, the project, and a
> **numbered list of product names**. **No prices.** A test asserts that no
> price from the input ever appears in the prompt."

Then open `proposal_gen/models.py`, point at the total:
> "The total is a property on the validated input, summed in Python. The
> docstring literally calls it 'the one and only source of the total — never the
> LLM.' So the model can write a weak sentence, but it cannot corrupt a price,
> drop a product, or invent a discount."

---

## 4. Run it (45 s)

Live, in the terminal:
```bash
uv run python -m proposal_gen -v
```
Talk over the log lines as they appear:
> "Four stages — load and validate, ask the model for prose, render HTML, print
> and verify the PDF. Here's the observability line: model, token counts,
> latency."

Open `output/proposal.pdf`:
> "Branded A4 — intro, each product with a benefit sentence, prices, the
> computed total, closing. The prose is fresh for this client; the numbers came
> from the file."

> (If you have no key or want a safe recording: `uv run python
> scripts/make_example.py` produces the same PDF from a canned reply — no API
> key, no network.)

---

## 5. Why it's reliable (75 s)

Don't read code line by line — name each guardrail in one breath and move on:

- **Input validation** — `pydantic` rejects a malformed YAML with a readable
  error and exit code 65, before any model call.
- **Strict model-reply contract** — the JSON reply is rejected unless it covers
  every product exactly once, **in order**, matched by **explicit index** (not
  by position, not by name). A reply describing four of five products fails
  loudly instead of silently producing a wrong document.
- **Repair loop** — a contract-breaking reply is fed back to the model once with
  the validation error, before giving up.
- **Typed errors + exit codes** — 65 input, 78 config, 69 LLM, 73 render. A
  wrapping script can tell "fix your YAML" from "the provider is down."
- **HTML autoescape** — client data and model prose can't inject HTML into the
  document.
- **Verified PDF** — success is only reported after Chrome exits 0 **and** the
  file exists, is non-empty, and starts with the `%PDF-` magic bytes.

One-liner to land it:
> "Every expected failure is typed and explained; an unexpected one still
> tracebacks — that's deliberate, a bug should look like a bug."

---

## 6. Tests and CI (45 s)

> "**162 tests, ~98% coverage**, all offline — no API key, no network — because
> the model is replaced by a fake that replays a canned reply. Lint, format, and
> **strict mypy** gate every change."

> "CI runs the full suite on **Ubuntu, macOS, and Windows**, plus a **Docker
> build** and a coverage gate. Dependabot keeps actions, dependencies, and the
> base image fresh."

Optionally show the green CI badge / the Actions tab.

---

## 7. AI evals — how I know the output is good (60 s)

> "Tests prove the *plumbing*. Evals prove the *product*."

- **Offline checks** (in CI): language match, length bounds, no invented numbers
  in the prose, no markdown artifacts — deterministic, no key.
- **Live eval report** (`docs/eval-report.md`): 30 real calls — **26
  contract-valid on the first reply, 1 recovered by the repair loop, 3
  truncated-JSON failures, and 27/27 on every quality check.**
- **Scheduled workflow** (`evals.yml`): runs **weekly**, and a **degradation
  gate** fails the run and **auto-opens a GitHub issue** if quality drops.

Land it:
> "That's the difference between 'we ran an eval once' and 'quality is
> monitored.'"

---

## 8. Limitations — stated honestly (30 s)

> "I'm deliberately honest about what it doesn't do:"
- One branded template; the currency and date format are Russian, template-level.
- The prose is checked for shape, grounding, and safety — **not** for
  persuasiveness. Whether a benefit line actually *sells* needs human judgment.
- Prompt injection is **bounded, not prevented** — a hostile name can influence
  a sentence, but never a number, the structure, HTML, or a secret.
- A human reviews the proposal before it's sent to a client.

Closing line:
> "Small on purpose. The value isn't the line count — it's the production
> discipline around a single model call."

---

### Cheat sheet (keep on screen)

| Beat | Command / file |
|---|---|
| Input | `data/products.yaml` |
| Boundary | `proposal_gen/llm.py` → `build_prompt`; `models.py` → `ProposalInput.total` |
| Run | `uv run python -m proposal_gen -v` |
| No-key run | `uv run python scripts/make_example.py` |
| Eval report | `docs/eval-report.md` |
| Numbers | 162 tests · ~98% coverage · 3 OSes · 26/1/3 eval · 27/27 checks |
