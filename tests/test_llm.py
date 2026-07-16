from decimal import Decimal

import pytest

from proposal_gen.errors import LLMError
from proposal_gen.llm import build_prompt, request_content, strip_code_fence
from proposal_gen.models import Product, ProposalInput
from tests.conftest import FakeProvider


@pytest.fixture
def sample_input() -> ProposalInput:
    return ProposalInput(
        client="ООО «Ромашка»",
        project="Bathroom",
        products=[
            Product(name="Mixer", price=Decimal("8900")),
            Product(name="Mirror", price=Decimal("6700")),
        ],
    )


def test_prompt_contains_names_but_never_prices(sample_input):
    prompt = build_prompt(sample_input, "InteriorPro", "Turnkey interiors")
    assert "Mixer" in prompt and "Mirror" in prompt
    assert "8900" not in prompt and "6700" not in prompt  # prices never reach the LLM


def test_prompt_numbers_products_by_index(sample_input):
    prompt = build_prompt(sample_input, "S", "T")
    assert "0. Mixer" in prompt and "1. Mirror" in prompt


@pytest.mark.parametrize(
    "wrapped",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        '```\n{"a": 1}\n```',
        '  ```json\n{"a": 1}\n```  ',
    ],
)
def test_strip_code_fence_variants(wrapped):
    assert strip_code_fence(wrapped) == '{"a": 1}'


def test_unclosed_fence_raises():
    with pytest.raises(LLMError, match="fence"):
        strip_code_fence('```json\n{"a": 1}')


def test_request_content_happy_path(canned_response):
    provider = FakeProvider(canned_response)
    content = request_content(provider, "prompt", expected_count=5)
    assert len(content.items) == 5
    assert provider.prompts == ["prompt"]


def test_request_content_rejects_invalid_json():
    provider = FakeProvider("this is not json")
    with pytest.raises(LLMError, match="not valid JSON"):
        request_content(provider, "prompt", expected_count=1)


def test_request_content_rejects_wrong_count(canned_response):
    provider = FakeProvider(canned_response)  # 5 items
    with pytest.raises(LLMError, match="in order"):
        request_content(provider, "prompt", expected_count=3)
