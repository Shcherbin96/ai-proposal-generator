"""Pipeline orchestration: input file -> LLM prose -> HTML -> PDF.

Numbers never pass through the LLM: prices and the total come from the
validated input (models.load_input) and are inserted in Python.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from proposal_gen import config
from proposal_gen.llm import LLMProvider, build_prompt, request_content
from proposal_gen.models import load_input
from proposal_gen.render import html_to_pdf, render_html

logger = logging.getLogger(__name__)


def generate(
    data_path: Path,
    provider: LLMProvider,
    out_pdf: Path | None = None,
    max_repairs: int = 1,
    today: date | None = None,
) -> Path:
    logger.info("Stage 1/4: loading input from %s", data_path)
    data = load_input(data_path)
    logger.info("Loaded %d products for client %r", len(data.products), data.client)

    logger.info("Stage 2/4: requesting prose from the LLM")
    prompt = build_prompt(data, config.SELLER["name"], config.SELLER["tagline"])
    content = request_content(
        provider, prompt, expected_count=len(data.products), max_repairs=max_repairs
    )
    logger.info("LLM content validated: %d descriptions", len(content.items))

    logger.info("Stage 3/4: rendering HTML")
    today = today or date.today()
    items = [
        {"name": p.name, "price": p.price, "description": item.description}
        for p, item in zip(data.products, content.items, strict=True)
    ]
    html = render_html(
        config.TEMPLATE,
        {
            "seller": config.SELLER,
            "client": data.client,
            "project": data.project,
            "date": today.strftime("%d.%m.%Y"),
            "intro": content.intro,
            "items": items,
            "total": data.total,
            "closing": content.closing,
        },
    )

    logger.info("Stage 4/4: printing PDF")
    out_pdf = out_pdf or (config.OUTPUT / "proposal.pdf")
    html_to_pdf(html, out_pdf)
    return out_pdf


if __name__ == "__main__":  # pragma: no cover
    # Kept for backward compatibility: `python -m proposal_gen.generate` was the
    # originally documented entry point. Import inside the block — a top-level
    # import of cli would be circular (cli imports generate).
    from proposal_gen.cli import main

    raise SystemExit(main())
