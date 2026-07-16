"""Regenerate the example PDF and README screenshot without any API key.

Uses the canned LLM response from tests/fixtures — the same bytes a good
model reply contains — so the artifact is reproducible offline.

Run: uv run python scripts/make_example.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from proposal_gen.generate import generate  # noqa: E402


class CannedProvider:
    """Replays the test fixture; no network, no API key."""

    def complete(self, prompt: str) -> str:
        return (ROOT / "tests" / "fixtures" / "llm_response.json").read_text(encoding="utf-8")


if __name__ == "__main__":
    pdf = generate(ROOT / "data" / "products.yaml", CannedProvider())
    print(f"Example PDF: {pdf}")
    print("Screenshot:  sips -s format png output/proposal.pdf --out docs/example-proposal.png")
