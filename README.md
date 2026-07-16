# AI Proposal Generator (КП-генератор)

[![CI](https://github.com/Shcherbin96/ai-proposal-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/Shcherbin96/ai-proposal-generator/actions/workflows/ci.yml)

Generates a **branded commercial proposal (КП) as a PDF** from a simple product list. An LLM writes the intro, per-product benefit descriptions, and closing; deterministic business data is validated and rendered into an A4 PDF via headless Chrome.

Inspired by a real workflow: turning a product list into a ready commercial proposal — cutting it from ~3 hours of manual work to ~2 minutes.

## How it works

```text
products.yaml → schema validation → LLM prose → response validation
              → auto-escaped Jinja2 template → headless Chrome → proposal.pdf
```

**Design choice that matters:** prices and totals come only from validated input and are calculated in Python. The LLM never receives or calculates prices. Its output is accepted only when every requested item has an indexed description.

## Run

Requirements: Python 3.12+, `uv`, and Google Chrome or Chromium.

```bash
uv sync --locked
cp .env.example .env        # configure GEMINI_API_KEY locally
uv run python -m proposal_gen.generate
uv run python -m proposal_gen.generate my.yaml --output output/client-proposal.pdf
```

Input format (`data/products.yaml`):

```yaml
client: "ООО «Ромашка»"
project: "Ванная комната, 6 м²"
products:
  - name: "Смеситель Grohe Eurosmart"
    price: 8900
```

Expected failures return a non-zero exit code with a stable error type, for example `input_validation_error`, `llm_response_error`, or `pdf_render_error`.

## Tests

Tests do not call a real LLM or browser.

```bash
uv run python -m unittest discover -s tests -v
```

## Tech stack

Python 3.12 · Google Gemini via an OpenAI-compatible API · Jinja2 · headless Chrome · `uv` · GitHub Actions.

## Security

- Keep `GEMINI_API_KEY` only in the local `.env`; `.env` is ignored by Git.
- Input YAML and LLM JSON are validated before use.
- Jinja2 auto-escaping prevents input or generated copy from being interpreted as arbitrary HTML.
- Prices and totals are never delegated to the LLM.

## Customization

Seller information is configured in `proposal_gen/config.py`; layout and branding live in `proposal_gen/template.html`.
