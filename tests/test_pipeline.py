import logging
from datetime import date
from pathlib import Path

import pytest

from proposal_gen import config, render
from proposal_gen.errors import RenderError
from proposal_gen.generate import generate
from proposal_gen.render import find_chrome
from tests.conftest import FakeProvider

SAMPLE = Path(__file__).parents[1] / "data" / "products.yaml"


def _chrome_available() -> bool:
    try:
        find_chrome()
        return True
    except RenderError:
        return False


@pytest.mark.skipif(not _chrome_available(), reason="Chrome/Chromium not installed")
def test_full_pipeline_offline(tmp_path, canned_response, caplog, monkeypatch):
    """Whole pipeline with the canned LLM reply: YAML in, verified PDF out.

    The intermediate HTML is captured via a spy (html_to_pdf deletes it on
    success), so we can assert on document content without touching the LLM.
    """
    captured = {}
    real_html_to_pdf = render.html_to_pdf

    def spy(html, out_pdf):
        captured["html"] = html
        real_html_to_pdf(html, out_pdf)

    monkeypatch.setattr("proposal_gen.generate.html_to_pdf", spy)

    provider = FakeProvider(canned_response)
    out = tmp_path / "proposal.pdf"
    with caplog.at_level(logging.DEBUG):
        result = generate(SAMPLE, provider, out_pdf=out)

    assert result == out
    assert out.read_bytes()[:5] == b"%PDF-"
    # every pipeline stage is observable
    for fragment in ("Stage 1/4", "Stage 2/4", "Stage 3/4", "Stage 4/4"):
        assert fragment in caplog.text
    # total computed in Python from input prices: 8900+21500+14200+6700+3400
    assert "54 700" in captured["html"]
    # prices never reach the LLM
    assert "8900" not in provider.prompts[0]
    assert "21500" not in provider.prompts[0]


def test_pipeline_validates_input_before_calling_llm(tmp_path, canned_response):
    """A broken input file must fail fast — the provider must never be called."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("client: c\nproject: p\nproducts: []\n", encoding="utf-8")
    provider = FakeProvider(canned_response)
    from proposal_gen.errors import InputError

    with pytest.raises(InputError):
        generate(bad, provider, out_pdf=tmp_path / "x.pdf")
    assert provider.prompts == []  # LLM was never consulted


def test_pipeline_plumbs_max_repairs_to_the_repair_loop(tmp_path, canned_response, monkeypatch):
    """max_repairs passed to generate() must reach request_content's loop:
    a bad first reply followed by a good one succeeds in exactly two calls.
    PDF rendering is stubbed out — this test is about the LLM plumbing, not Chrome."""
    monkeypatch.setattr(
        "proposal_gen.generate.html_to_pdf",
        lambda html, out_pdf: out_pdf.write_bytes(b"%PDF-stub"),
    )
    provider = FakeProvider(["this is not json", canned_response])
    out = tmp_path / "proposal.pdf"
    result = generate(SAMPLE, provider, out_pdf=out, max_repairs=1)
    assert result == out
    assert len(provider.prompts) == 2  # original prompt + one repair prompt


def _spy_html_to_pdf(monkeypatch):
    """Stub Chrome and return a dict that will hold the captured HTML."""
    captured = {}

    def spy(html, out_pdf):
        captured["html"] = html
        out_pdf.write_bytes(b"%PDF-stub")

    monkeypatch.setattr("proposal_gen.generate.html_to_pdf", spy)
    return captured


def test_generate_uses_injected_date_for_reproducible_output(
    tmp_path, canned_response, monkeypatch
):
    """An explicit `today` must reach the rendered document instead of date.today(),
    so output is reproducible in tests and snapshots. PDF rendering is stubbed out
    via a spy that captures the HTML Chrome would have received."""
    captured = _spy_html_to_pdf(monkeypatch)
    provider = FakeProvider(canned_response)
    out = tmp_path / "proposal.pdf"
    generate(SAMPLE, provider, out_pdf=out, today=date(2026, 1, 15))
    assert "15.01.2026" in captured["html"]


def test_generate_uses_seller_override_from_yaml(tmp_path, canned_response, monkeypatch):
    """A `seller` block in the input YAML overrides config.SELLER for this document."""
    captured = _spy_html_to_pdf(monkeypatch)
    # Start from the real sample (5 products, matching the canned LLM reply's
    # 5 indexed items) and append a seller override.
    data_path = tmp_path / "products.yaml"
    text = SAMPLE.read_text(encoding="utf-8")
    text += (
        "seller:\n"
        "  name: Custom Seller Co\n"
        "  tagline: Custom tagline\n"
        "  contacts: custom@example.com\n"
    )
    data_path.write_text(text, encoding="utf-8")
    provider = FakeProvider(canned_response)
    generate(data_path, provider, out_pdf=tmp_path / "out.pdf")
    assert "Custom Seller Co" in captured["html"]
    assert config.SELLER["name"] not in captured["html"]


def test_generate_falls_back_to_config_seller_without_override(
    tmp_path, canned_response, monkeypatch
):
    """No `seller` block in the input YAML: config.SELLER is used, as before."""
    captured = _spy_html_to_pdf(monkeypatch)
    provider = FakeProvider(canned_response)
    generate(SAMPLE, provider, out_pdf=tmp_path / "out.pdf")
    assert config.SELLER["name"] in captured["html"]
