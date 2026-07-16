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
    # .strip(): a stray space or trailing newline in .env would otherwise
    # surface as a confusing "missing file" error.
    override = os.getenv("CHROME_PATH", "").strip()
    if override:
        if Path(override).is_file():
            return override
        raise RenderError(f"CHROME_PATH points to a missing file: {override}")
    for name in _CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    system = platform.system()
    extra: list[str] = []
    if system == "Darwin":
        extra = list(_MAC_APPS)
    elif system == "Windows":
        extra = list(_WINDOWS_PATHS)
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            # Per-user installs (no admin rights) live under %LOCALAPPDATA%.
            extra.append(str(Path(local_appdata) / "Google/Chrome/Application/chrome.exe"))
    for path in extra:
        if Path(path).is_file():
            return path
    raise RenderError(
        "Google Chrome / Chromium not found. Install it, or set CHROME_PATH "
        "to the full path of the browser binary."
    )


def money(value: Decimal | int) -> str:
    """8900 -> '8 900'; 8900.50 -> '8 900,50'. Formatting lives in code, not in the template.

    Integral values render with no decimals; fractional values render with
    exactly two, so displayed line items always sum to the displayed total.
    Relies on upstream input validation (price gt=0, decimal_places=2):
    NaN, negatives and sub-kopeck precision never reach here.
    """
    value = Decimal(value)
    s = f"{value:,.0f}" if value == value.to_integral_value() else f"{value:,.2f}"
    # Thousands comma -> space must run BEFORE decimal point -> comma, or the
    # freshly introduced decimal comma would be clobbered into a space.
    return s.replace(",", " ").replace(".", ",")


def render_html(template_path: Path, context: dict[str, object]) -> str:
    """Render the proposal template with autoescaping and strict variables."""
    env = Environment(
        loader=FileSystemLoader(template_path.parent),
        autoescape=True,
        undefined=StrictUndefined,
    )
    env.filters["money"] = money
    # Fonts live next to the template, but the intermediate .html is written
    # next to the OUTPUT pdf — a relative font URL would break there. Inject
    # an absolute file:// URI instead (URI-safe chars only, autoescape-inert).
    context = {**context, "fonts_dir": (template_path.parent / "fonts").as_uri()}
    return env.get_template(template_path.name).render(context)


def html_to_pdf(html: str, out_pdf: Path) -> None:
    """Print HTML to PDF via headless Chrome; verify the output is a real PDF."""
    chrome = find_chrome()
    out_html = out_pdf.with_suffix(".html")
    try:
        # RenderError's exit code 73 is EX_CANTCREAT ("output file cannot be
        # created") — an unwritable output location belongs there, not in a
        # raw PermissionError traceback with a generic exit 1.
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        # A stale PDF from a previous run must never satisfy the verification below.
        out_pdf.unlink(missing_ok=True)
        out_html.write_text(html, encoding="utf-8")
    except OSError as exc:
        raise RenderError(f"Cannot write output files at {out_pdf.parent}: {exc}") from exc
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
        # encoding/errors instead of text=True: Chrome's stderr is not
        # guaranteed UTF-8 on non-UTF-8 locales (Windows); never let a
        # diagnostic message turn into a UnicodeDecodeError.
        result = subprocess.run(
            cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=120
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderError("Chrome timed out while rendering the PDF") from exc
    if result.returncode != 0:
        tail = result.stderr.strip()[-500:]
        raise RenderError(f"Chrome failed (exit {result.returncode}): {tail}")
    if not out_pdf.is_file() or out_pdf.stat().st_size == 0:
        raise RenderError(f"Chrome exited 0 but produced no PDF at {out_pdf}")
    if out_pdf.read_bytes()[:5] != b"%PDF-":
        raise RenderError(f"Output at {out_pdf} is not a valid PDF")
    # Success: the intermediate .html has served its purpose — remove it. On
    # any failure above it is deliberately left in place so the exact input
    # Chrome saw can be inspected for debugging.
    out_html.unlink(missing_ok=True)
    logger.info("PDF written: %s (%d bytes)", out_pdf, out_pdf.stat().st_size)
