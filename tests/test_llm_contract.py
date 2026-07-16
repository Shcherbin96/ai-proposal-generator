import pytest

from proposal_gen.errors import LLMError
from proposal_gen.models import validate_llm_content


def payload(indices, intro="Hello", closing="Bye"):
    return {
        "intro": intro,
        "items": [{"index": i, "description": f"desc {i}"} for i in indices],
        "closing": closing,
    }


def test_valid_response_passes():
    content = validate_llm_content(payload([0, 1, 2]), expected_count=3)
    assert content.intro == "Hello"
    assert [i.index for i in content.items] == [0, 1, 2]


def test_extra_keys_from_model_are_tolerated():
    raw = payload([0])
    raw["confidence"] = 0.9
    raw["items"][0]["note"] = "junk"
    assert validate_llm_content(raw, expected_count=1).items[0].description == "desc 0"


@pytest.mark.parametrize(
    "raw,fragment",
    [
        (payload([0]), "in order"),
        (payload([0, 1, 2]), "in order"),
        (payload([1, 0]), "in order"),
        (payload([0, 0]), "in order"),
        (payload([0, 1], intro=""), "intro"),
        (payload([0, 1], closing="  "), "closing"),
        ({"intro": "x", "closing": "y"}, "items"),
        ({"items": [], "closing": "y"}, "intro"),
        ("not a dict", "validation"),
        (payload([-1, 0]), "index"),  # negative index
        (payload([0, 0.5]), "index"),  # fractional index
        (payload(["abc", 1]), "index"),  # non-integer index
    ],
)
def test_bad_responses_rejected(raw, fragment):
    with pytest.raises(LLMError, match=fragment):
        validate_llm_content(raw, expected_count=2)


def test_oversized_bad_response_error_is_capped():
    """An adversarial 100-item response must not echo the full list back."""
    with pytest.raises(LLMError) as exc_info:
        validate_llm_content(payload(list(range(100))), expected_count=2)
    message = str(exc_info.value)
    assert "(100 total)" in message
    assert len(message) < 500


def test_empty_description_rejected():
    raw = {
        "intro": "x",
        "items": [{"index": 0, "description": ""}],
        "closing": "y",
    }
    with pytest.raises(LLMError, match="description"):
        validate_llm_content(raw, expected_count=1)
