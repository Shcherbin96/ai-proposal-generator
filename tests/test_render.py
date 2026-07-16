import os
import subprocess
import sys
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
    assert money(8900) == "8 900"


def test_money_formats_fractional_with_comma_decimal():
    assert money(Decimal("8900.50")) == "8 900,50"
    # A whole value stays clean even when written with a fractional part.
    assert money(Decimal("8900.00")) == "8 900"


def _parse_money(rendered: str) -> Decimal:
    return Decimal(rendered.replace(" ", "").replace(",", "."))


def test_money_line_items_sum_to_rendered_total():
    # The displayed numbers must obey document arithmetic: rendering must not
    # round line items independently of the total.
    prices = [Decimal("8900.50"), Decimal("21500.50")]
    total = sum(prices, Decimal(0))
    assert money(total) == "30 401"
    rendered_sum = sum((_parse_money(money(p)) for p in prices), Decimal(0))
    assert rendered_sum == _parse_money(money(total))


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


def test_windows_per_user_chrome_found_via_localappdata(monkeypatch, tmp_path):
    # Per-user Windows installs (no admin rights) live under %LOCALAPPDATA%,
    # not Program Files.
    monkeypatch.delenv("CHROME_PATH", raising=False)
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr("platform.system", lambda: "Windows")
    exe = tmp_path / "Google" / "Chrome" / "Application" / "chrome.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert find_chrome() == str(exe)


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
    # sys.executable exists on every platform and exits nonzero when fed
    # Chrome's flags, exercising the "Chrome failed" branch portably.
    monkeypatch.setenv("CHROME_PATH", sys.executable)
    with pytest.raises(RenderError, match="failed"):
        html_to_pdf("<html></html>", tmp_path / "out.pdf")


def test_html_to_pdf_timeout_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("CHROME_PATH", sys.executable)

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="chrome", timeout=120)

    monkeypatch.setattr("proposal_gen.render.subprocess.run", fake_run)
    with pytest.raises(RenderError, match="timed out"):
        html_to_pdf("<html></html>", tmp_path / "out.pdf")


def test_html_to_pdf_rejects_exit_zero_without_output(monkeypatch, tmp_path):
    monkeypatch.setenv("CHROME_PATH", sys.executable)
    monkeypatch.setattr(
        "proposal_gen.render.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
    )
    with pytest.raises(RenderError, match="no PDF"):
        html_to_pdf("<html></html>", tmp_path / "out.pdf")


def test_html_to_pdf_rejects_wrong_magic_bytes(monkeypatch, tmp_path):
    monkeypatch.setenv("CHROME_PATH", sys.executable)
    out = tmp_path / "out.pdf"

    def fake_run(*args, **kwargs):
        out.write_bytes(b"not a pdf")
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr("proposal_gen.render.subprocess.run", fake_run)
    with pytest.raises(RenderError, match="not a valid PDF"):
        html_to_pdf("<html></html>", out)


def test_intermediate_html_deleted_after_successful_pdf(monkeypatch, tmp_path):
    monkeypatch.setenv("CHROME_PATH", sys.executable)
    out = tmp_path / "out.pdf"

    def fake_run(*args, **kwargs):
        out.write_bytes(b"%PDF-1.7 fake")
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr("proposal_gen.render.subprocess.run", fake_run)
    html_to_pdf("<html></html>", out)
    assert out.is_file()
    assert not out.with_suffix(".html").exists()


def test_intermediate_html_kept_on_failure_for_debugging(monkeypatch, tmp_path):
    monkeypatch.setenv("CHROME_PATH", sys.executable)
    out = tmp_path / "out.pdf"
    with pytest.raises(RenderError):
        html_to_pdf("<html></html>", out)
    assert out.with_suffix(".html").is_file()


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
def test_html_to_pdf_wraps_filesystem_oserror_as_render_error(monkeypatch, tmp_path):
    # Exit code 73 is EX_CANTCREAT: "output file cannot be created". An
    # unwritable output directory must surface as RenderError, not as a raw
    # PermissionError traceback with a generic exit 1.
    monkeypatch.setenv("CHROME_PATH", sys.executable)
    read_only_dir = tmp_path / "ro"
    read_only_dir.mkdir()
    read_only_dir.chmod(0o444)
    try:
        with pytest.raises(RenderError, match="Cannot write"):
            html_to_pdf("<html></html>", read_only_dir / "x.pdf")
    finally:
        # Restore permissions so pytest can clean up tmp_path.
        read_only_dir.chmod(0o755)
