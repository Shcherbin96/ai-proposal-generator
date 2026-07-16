"""Generate a branded PDF proposal from validated YAML input."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from proposal_gen import config
from proposal_gen.errors import (
    ConfigurationError,
    LLMResponseError,
    PDFRenderError,
    ProposalGeneratorError,
)
from proposal_gen.models import GeneratedCopy, ProposalData, load_proposal_data, parse_generated_copy

PROMPT = """Ты — менеджер компании «{seller}» ({tagline}). Составь коммерческое предложение для клиента.
Клиент: {client}. Проект: {project}.
Товары (в этом порядке, индекс обязателен):
{products}

Задача:
- intro: короткое вступление (2–3 предложения, по делу, без воды).
- для КАЖДОГО товара — описание пользы в 1–2 предложения. НЕ выдумывай технических характеристик и цифр, которых не знаешь.
- closing: короткое закрытие с мягким призывом.

Верни СТРОГО JSON без markdown:
{{"intro": "...", "items": [{{"index": 1, "description": "..."}}], "closing": "..."}}
Порядок и количество items должны строго совпадать со списком товаров."""

LLMCall = Callable[[str], Any]
PDFRenderer = Callable[[str, Path], None]


def build_prompt(data: ProposalData) -> str:
    """Build a deterministic prompt without exposing prices to the LLM."""

    products = "\n".join(
        f"{index}. {product.name}" for index, product in enumerate(data.products, start=1)
    )
    return PROMPT.format(
        seller=config.SELLER["name"],
        tagline=config.SELLER["tagline"],
        client=data.client,
        project=data.project,
        products=products,
    )


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        lines = lines[1:-1]
    else:
        lines = lines[1:]
    return "\n".join(lines).strip()


def _decode_llm_json(text: str | None) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        raise LLMResponseError("LLM returned an empty response.")

    try:
        payload = json.loads(_strip_code_fence(text))
    except json.JSONDecodeError as exc:
        raise LLMResponseError("LLM returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise LLMResponseError("LLM response must be a JSON object.")
    return payload


def _llm_json(prompt: str) -> dict[str, Any]:
    """Call the configured OpenAI-compatible provider and decode JSON."""

    if not config.LLM_API_KEY:
        raise ConfigurationError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and configure it locally."
        )

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_BASE_URL,
            timeout=config.LLM_TIMEOUT_SECONDS,
            max_retries=config.LLM_MAX_RETRIES,
        )
        response = client.chat.completions.create(
            model=config.MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        content = response.choices[0].message.content
    except (IndexError, AttributeError) as exc:
        raise LLMResponseError("LLM provider returned an unexpected response shape.") from exc
    except Exception as exc:
        raise LLMResponseError(
            "LLM request failed. Check local configuration and provider availability."
        ) from exc

    return _decode_llm_json(content)


def _format_money(value: Decimal) -> str:
    if value == value.to_integral_value():
        return f"{value:,.0f}".replace(",", " ")
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def render_html(
    data: ProposalData,
    generated: GeneratedCopy,
    generated_on: date | None = None,
) -> str:
    """Render escaped HTML using a strict Jinja environment."""

    environment = Environment(
        loader=FileSystemLoader(config.ROOT / "proposal_gen"),
        autoescape=select_autoescape(enabled_extensions=("html", "xml"), default=True),
        undefined=StrictUndefined,
    )
    environment.filters["money"] = _format_money
    template = environment.get_template("template.html")
    items = [
        {
            "name": product.name,
            "price": product.price,
            "description": description,
        }
        for product, description in zip(
            data.products,
            generated.descriptions,
            strict=True,
        )
    ]
    return template.render(
        seller=config.SELLER,
        client=data.client,
        project=data.project,
        date=(generated_on or date.today()).strftime("%d.%m.%Y"),
        intro=generated.intro,
        items=items,
        total=data.total,
        closing=generated.closing,
    )


def _find_chrome() -> Path:
    executable_names = (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
    )
    for name in executable_names:
        resolved = shutil.which(name)
        if resolved:
            return Path(resolved)

    candidates = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
    ]
    for env_name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        root = os.getenv(env_name)
        if root:
            candidates.append(Path(root) / "Google/Chrome/Application/chrome.exe")

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    raise PDFRenderError(
        "Google Chrome or Chromium was not found. Install a supported browser or add it to PATH."
    )


def _render_pdf(html: str, out_pdf: Path) -> None:
    """Render HTML to PDF with a locally installed headless browser."""

    out_pdf = out_pdf.resolve()
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    chrome = _find_chrome()
    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".html",
            dir=out_pdf.parent,
            delete=False,
        ) as temp_file:
            temp_file.write(html)
            temp_path = Path(temp_file.name)

        subprocess.run(
            [
                str(chrome),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={out_pdf}",
                temp_path.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise PDFRenderError("PDF rendering timed out after 60 seconds.") from exc
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PDFRenderError("Headless browser failed to render the PDF.") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    if not out_pdf.is_file() or out_pdf.stat().st_size == 0:
        raise PDFRenderError("Browser process completed without producing a valid PDF file.")


def generate(
    data_path: str | Path,
    output_path: str | Path | None = None,
    *,
    llm_call: LLMCall = _llm_json,
    pdf_renderer: PDFRenderer = _render_pdf,
) -> Path:
    """Run the validated input → LLM prose → escaped HTML → PDF pipeline."""

    data = load_proposal_data(data_path)
    payload = llm_call(build_prompt(data))
    generated = parse_generated_copy(payload, expected_items=len(data.products))
    html = render_html(data, generated)

    out_pdf = Path(output_path) if output_path else config.OUTPUT / "proposal.pdf"
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf_renderer(html, out_pdf)
    return out_pdf


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a branded PDF commercial proposal from YAML input."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=config.DATA / "products.yaml",
        help="Path to proposal YAML (default: data/products.yaml).",
    )
    parser.add_argument(
        "--output",
        default=config.OUTPUT / "proposal.pdf",
        help="Destination PDF path (default: output/proposal.pdf).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        pdf = generate(args.input, args.output)
    except ProposalGeneratorError as exc:
        print(f"ERROR [{exc.error_type}]: {exc}", file=sys.stderr)
        return 1

    print(f"Proposal ready: {pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
