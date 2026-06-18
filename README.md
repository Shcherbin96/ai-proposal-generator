# AI Proposal Generator (КП-генератор)

Generates a **branded commercial proposal (КП) as a PDF** from a simple product list. An LLM writes the intro, per-product benefit descriptions, and closing; the result is rendered into a clean A4 PDF via headless Chrome.

Inspired by a real workflow: turning a product list into a ready commercial proposal — cutting it from ~3 hours of manual work to ~2 minutes.

## How it works

```
products.yaml  →  LLM (Gemini) writes intro + descriptions + closing
               →  Jinja2 HTML template (branded)
               →  headless Chrome  →  proposal.pdf
```

**Design choice that matters:** prices and the total are taken from the input and summed **in Python** — never trusted to the LLM. The model only writes prose. This keeps numbers accurate (no hallucinated prices) while the text stays persuasive.

## Run

```bash
uv sync
cp .env.example .env        # add GEMINI_API_KEY
uv run python -m proposal_gen.generate            # uses data/products.yaml
uv run python -m proposal_gen.generate my.yaml    # or your own list
# → output/proposal.pdf
```

Input format (`data/products.yaml`):
```yaml
client: "ООО «Ромашка»"
project: "Ванная комната, 6 м²"
products:
  - name: "Смеситель Grohe Eurosmart"
    price: 8900
```

## Tech stack

Python 3.12 · Google Gemini via OpenAI-compatible API · Jinja2 · headless Chrome (HTML→PDF) · `uv`.

## Notes

LLM writes only prose; all numbers come from your data. Branding (company, fonts, colors) lives in `proposal_gen/config.py` and `proposal_gen/template.html` — change them for your business.
