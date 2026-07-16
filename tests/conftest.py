import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


class FakeProvider:
    """LLMProvider test double that replays a canned response. No network."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


@pytest.fixture
def canned_response() -> str:
    return (FIXTURES / "llm_response.json").read_text(encoding="utf-8")


@pytest.fixture
def canned_payload(canned_response) -> dict:
    return json.loads(canned_response)
