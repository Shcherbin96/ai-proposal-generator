from decimal import Decimal

import pytest
from jinja2 import UndefinedError

from proposal_gen import config
from proposal_gen.errors import RenderError
from proposal_gen.render import find_chrome, html_to_pdf, money, render_html


def full_context(**overrides):
    ctx = {
        "seller": config.SELLER,
        "client": "Client",
        "project": "Project",
        "date": "16.07.2026",
        "intro": "Intro",
        "items": [{"name": "N", "price": Decimal("8900"), "description": "D"}],
        "total": Decimal("8900"),
        "closing": "Closing",
    }
    ctx.update(overrides)
    return ctx


def test_money_formats_with_thin_spaces():
    assert money(Decimal("1234567")) == "1 234 567"
    assert money(Decimal("8900")) == "8 900"


def test_html_injection_is_escaped():
    html = render_html(config.TEMPLATE, full_context(client="<script>alert(1)</script>"))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_llm_prose_is_escaped_too():
    html = render_html(config.TEMPLATE, full_context(intro='<img src=x onerror="pwn()">'))
    assert '<img src=x onerror="pwn()">' not in html
    assert "&lt;img" in html


def test_missing_variable_fails_loudly():
    ctx = full_context()
    del ctx["closing"]
    with pytest.raises(UndefinedError):  # StrictUndefined turns missing vars into errors
        render_html(config.TEMPLATE, ctx)


def test_chrome_path_env_override(monkeypatch, tmp_path):
    fake = tmp_path / "chrome"
    fake.write_text("#!/bin/sh\n")
    monkeypatch.setenv("CHROME_PATH", str(fake))
    assert find_chrome() == str(fake)


def test_chrome_path_env_missing_file_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("CHROME_PATH", str(tmp_path / "nope"))
    with pytest.raises(RenderError, match="CHROME_PATH"):
        find_chrome()


def test_chrome_not_found_raises_actionable_error(monkeypatch):
    monkeypatch.delenv("CHROME_PATH", raising=False)
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: False)
    with pytest.raises(RenderError, match="not found"):
        find_chrome()


def _chrome_available() -> bool:
    try:
        find_chrome()
        return True
    except RenderError:
        return False


@pytest.mark.skipif(not _chrome_available(), reason="Chrome/Chromium not installed")
def test_html_to_pdf_produces_valid_pdf(tmp_path):
    out = tmp_path / "out.pdf"
    html_to_pdf("<html><body><h1>Test</h1></body></html>", out)
    assert out.is_file()
    assert out.stat().st_size > 1000
    assert out.read_bytes()[:5] == b"%PDF-"


def test_html_to_pdf_rejects_failed_chrome(monkeypatch, tmp_path):
    # /usr/bin/false, not /bin/false: macOS never shipped /bin/false (only
    # /usr/bin/false); /usr/bin/false exists on both macOS and Linux.
    monkeypatch.setenv("CHROME_PATH", "/usr/bin/false")
    with pytest.raises(RenderError, match="failed"):
        html_to_pdf("<html></html>", tmp_path / "out.pdf")
