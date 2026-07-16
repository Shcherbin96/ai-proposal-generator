"""HTML/PDF rendering: autoescaped Jinja2 + headless Chrome with verified output."""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from proposal_gen.errors import RenderError

logger = logging.getLogger(__name__)

_CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")
_MAC_APPS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)
_WINDOWS_PATHS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


def find_chrome() -> str:
    """Locate a Chrome/Chromium binary on Linux, macOS or Windows."""
    override = os.getenv("CHROME_PATH")
    if override:
        if Path(override).is_file():
            return override
        raise RenderError(f"CHROME_PATH points to a missing file: {override}")
    for name in _CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    system = platform.system()
    extra = _MAC_APPS if system == "Darwin" else _WINDOWS_PATHS if system == "Windows" else ()
    for path in extra:
        if Path(path).is_file():
            return path
    raise RenderError(
        "Google Chrome / Chromium not found. Install it, or set CHROME_PATH "
        "to the full path of the browser binary."
    )


def money(value: Decimal | int) -> str:
    """8900 -> '8 900'. Formatting lives in code, not in the template."""
    return f"{value:,.0f}".replace(",", " ")


def render_html(template_path: Path, context: dict[str, object]) -> str:
    """Render the proposal template with autoescaping and strict variables."""
    env = Environment(
        loader=FileSystemLoader(template_path.parent),
        autoescape=True,
        undefined=StrictUndefined,
    )
    env.filters["money"] = money
    return env.get_template(template_path.name).render(context)


def html_to_pdf(html: str, out_pdf: Path) -> None:
    """Print HTML to PDF via headless Chrome; verify the output is a real PDF."""
    chrome = find_chrome()
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    out_html = out_pdf.with_suffix(".html")
    out_html.write_text(html, encoding="utf-8")
    cmd = [
        chrome,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={out_pdf}",
        out_html.resolve().as_uri(),
    ]
    logger.info("Rendering PDF via %s", chrome)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired as exc:
        raise RenderError("Chrome timed out while rendering the PDF") from exc
    if result.returncode != 0:
        tail = result.stderr.strip()[-500:]
        raise RenderError(f"Chrome failed (exit {result.returncode}): {tail}")
    if not out_pdf.is_file() or out_pdf.stat().st_size == 0:
        raise RenderError(f"Chrome exited 0 but produced no PDF at {out_pdf}")
    if out_pdf.read_bytes()[:5] != b"%PDF-":
        raise RenderError(f"Output at {out_pdf} is not a valid PDF")
    logger.info("PDF written: %s (%d bytes)", out_pdf, out_pdf.stat().st_size)
