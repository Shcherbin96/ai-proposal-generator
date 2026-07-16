import logging
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from openai import OpenAIError

from proposal_gen.config import DEFAULT_MODEL, Settings
from proposal_gen.errors import LLMError
from proposal_gen.llm import (
    OpenAICompatProvider,
    build_prompt,
    request_content,
    strip_code_fence,
)
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


# --- OpenAICompatProvider with a mocked client (no network) ---


def _fake_response(content, usage=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=usage
    )


@pytest.fixture
def provider() -> OpenAICompatProvider:
    return OpenAICompatProvider(Settings(api_key="test-key"))


def test_provider_wraps_openai_errors_as_llm_error(provider):
    create = Mock(side_effect=OpenAIError("boom"))
    with (
        patch.object(provider._client.chat.completions, "create", create),
        pytest.raises(LLMError, match="request failed"),
    ):
        provider.complete("prompt")


def test_provider_rejects_empty_choices(provider):
    create = Mock(return_value=SimpleNamespace(choices=[]))
    with (
        patch.object(provider._client.chat.completions, "create", create),
        pytest.raises(LLMError, match="no choices"),
    ):
        provider.complete("prompt")


@pytest.mark.parametrize("content", [None, ""])
def test_provider_rejects_empty_completion(provider, content):
    create = Mock(return_value=_fake_response(content))
    with (
        patch.object(provider._client.chat.completions, "create", create),
        pytest.raises(LLMError, match="empty completion"),
    ):
        provider.complete("prompt")


def test_provider_happy_path_passes_model_and_temperature(provider):
    # json_mode defaults to True (Settings default), so response_format is expected.
    create = Mock(return_value=_fake_response("prose"))
    with patch.object(provider._client.chat.completions, "create", create):
        assert provider.complete("prompt") == "prose"
    create.assert_called_once_with(
        model=DEFAULT_MODEL,
        messages=[{"role": "user", "content": "prompt"}],
        temperature=0.4,
        response_format={"type": "json_object"},
    )


def test_provider_json_mode_off_omits_response_format():
    provider = OpenAICompatProvider(Settings(api_key="test-key", json_mode=False))
    create = Mock(return_value=_fake_response("prose"))
    with patch.object(provider._client.chat.completions, "create", create):
        assert provider.complete("prompt") == "prose"
    _, kwargs = create.call_args
    assert "response_format" not in kwargs


def test_provider_logs_observability_line_with_usage(provider, caplog):
    usage = SimpleNamespace(prompt_tokens=12, completion_tokens=34, total_tokens=46)
    create = Mock(return_value=_fake_response("prose", usage=usage))
    with (
        patch.object(provider._client.chat.completions, "create", create),
        caplog.at_level(logging.INFO),
    ):
        provider.complete("prompt")
    [record] = [r for r in caplog.records if r.message.startswith("LLM call:")]
    assert f"model={DEFAULT_MODEL}" in record.message
    assert "prompt_version=1" in record.message
    assert "tokens=12/34/46" in record.message
    assert "latency_ms=" in record.message


def test_provider_logs_observability_line_with_usage_none(provider, caplog):
    create = Mock(return_value=_fake_response("prose", usage=None))
    with (
        patch.object(provider._client.chat.completions, "create", create),
        caplog.at_level(logging.INFO),
    ):
        provider.complete("prompt")
    [record] = [r for r in caplog.records if r.message.startswith("LLM call:")]
    assert "tokens=n/a/n/a/n/a" in record.message
