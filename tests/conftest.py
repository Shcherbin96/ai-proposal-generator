import json
from pathlib import Path

import pytest

from proposal_gen.errors import RenderError
from proposal_gen.render import find_chrome

FIXTURES = Path(__file__).parent / "fixtures"


def chrome_available() -> bool:
    """Shared skipif guard for tests that need a real Chrome binary."""
    try:
        find_chrome()
        return True
    except RenderError:
        return False


class FakeProvider:
    """LLMProvider test double. No network.

    A single string replays forever (backward compatible with the original
    single-response double). A list is a one-shot queue: each call pops the
    next response, and popping an empty queue raises AssertionError — a test
    that asserts on an exact call count should fail loudly on one call too
    many, not silently replay stale data.
    """

    def __init__(self, response: str | list[str]) -> None:
        self.response = response
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if isinstance(self.response, list):
            if not self.response:
                raise AssertionError("FakeProvider queue exhausted — unexpected extra call")
            return self.response.pop(0)
        return self.response


@pytest.fixture
def canned_response() -> str:
    return (FIXTURES / "llm_response.json").read_text(encoding="utf-8")


@pytest.fixture
def canned_payload(canned_response) -> dict:
    return json.loads(canned_response)
