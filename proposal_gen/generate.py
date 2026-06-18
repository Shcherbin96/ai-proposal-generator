"""AI-генератор КП: данные о товарах → LLM пишет описания → брендированный PDF.

Запуск: uv run python -m proposal_gen.generate [data/products.yaml]
"""
import json
import shutil
import subprocess
import sys
from datetime import date

import yaml
from jinja2 import Template
from openai import OpenAI

from proposal_gen import config

PROMPT = """Ты — менеджер компании «{seller}» ({tagline}). Составь коммерческое предложение для клиента.
Клиент: {client}. Проект: {project}.
Товары (в этом порядке):
{products}

Задача:
- intro: короткое вступление (2–3 предложения, по делу, без воды).
- для КАЖДОГО товара — описание пользы в 1–2 предложения. НЕ выдумывай технических характеристик и цифр, которых не знаешь; пиши о пользе, качестве, удобстве.
- closing: короткое закрытие с мягким призывом.

Верни СТРОГО JSON без markdown:
{{"intro": "...", "items": [{{"name": "...", "description": "..."}}], "closing": "..."}}
Порядок items — строго как в списке товаров."""


def _llm_json(prompt: str) -> dict:
    client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
    resp = client.chat.completions.create(
        model=config.MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    text = resp.choices[0].message.content.strip()
    # на случай если модель завернёт в ```json ... ```
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    return json.loads(text)


def _render_pdf(html: str, out_pdf) -> None:
    """HTML → PDF через headless Chrome (как в ручном пайплайне Романа)."""
    chrome = (
        shutil.which("google-chrome")
        or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    )
    out_html = out_pdf.with_suffix(".html")
    out_html.write_text(html, encoding="utf-8")
    subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={out_pdf}", str(out_html)],
        check=True, stderr=subprocess.DEVNULL,
    )


def generate(data_path) -> str:
    data = yaml.safe_load(open(data_path, encoding="utf-8"))
    products = data["products"]

    prompt = PROMPT.format(
        seller=config.SELLER["name"], tagline=config.SELLER["tagline"],
        client=data["client"], project=data["project"],
        products="\n".join(f"- {p['name']}" for p in products),
    )
    ai = _llm_json(prompt)

    # цены берём из ВХОДА (не доверяем LLM цифры), описания — от LLM по порядку
    items = []
    for p, descr in zip(products, ai["items"]):
        items.append({"name": p["name"], "price": p["price"], "description": descr["description"]})
    total = sum(p["price"] for p in products)   # сумму считаем в Python, не у LLM

    html = Template((config.ROOT / "proposal_gen" / "template.html").read_text(encoding="utf-8")).render(
        seller=config.SELLER, client=data["client"], project=data["project"],
        date=date.today().strftime("%d.%m.%Y"),
        intro=ai["intro"], items=items, total=total, closing=ai["closing"],
    )

    config.OUTPUT.mkdir(exist_ok=True)
    out_pdf = config.OUTPUT / "proposal.pdf"
    _render_pdf(html, out_pdf)
    return str(out_pdf)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else config.DATA / "products.yaml"
    pdf = generate(path)
    print(f"✅ КП готово: {pdf}")
