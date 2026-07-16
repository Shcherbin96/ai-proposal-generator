"""Offline coverage for evals/checks.py — no network, runs in CI.

Import via `from evals.checks import ...`: pytest's rootdir insertion (via
tests/__init__.py forcing prepend import mode up to the repo root, the same
mechanism that makes `proposal_gen` importable here) makes the top-level
`evals` package importable too.
"""

from pathlib import Path

import pytest

from evals.checks import (
    CheckResult,
    check_language_match,
    check_length_bounds,
    check_no_invented_numbers,
    check_no_markdown_artifacts,
    run_all_checks,
)
from proposal_gen.models import (
    LLMContent,
    LLMItem,
    Product,
    ProposalInput,
    load_input,
    validate_llm_content,
)

SAMPLE = Path(__file__).parents[1] / "data" / "products.yaml"


def make_input(
    products=None, client="ООО «Ромашка»", project="Ванная комната, 6 м²"
) -> ProposalInput:
    products = products or [Product(name="Смеситель Grohe Eurosmart", price="8900")]
    return ProposalInput(client=client, project=project, products=products)


def make_content(intro="x", descriptions=("y",), closing="z") -> LLMContent:
    items = [LLMItem(index=i, description=d) for i, d in enumerate(descriptions)]
    return LLMContent(intro=intro, items=items, closing=closing)


# --- canned fixture + sample input: the "everything is fine" baseline -------


def test_canned_fixture_passes_all_checks(canned_payload):
    data = load_input(SAMPLE)
    content = validate_llm_content(canned_payload, expected_count=len(data.products))
    results = run_all_checks(data, content)
    failures = [r for r in results if not r.passed]
    assert failures == [], f"expected all checks to pass, got failures: {failures}"
    assert {r.name for r in results} == {
        "language_match",
        "length_bounds",
        "no_invented_numbers",
        "no_markdown_artifacts",
    }


# --- check_language_match ----------------------------------------------------


def test_language_match_passes_when_both_russian(canned_payload):
    data = load_input(SAMPLE)
    content = validate_llm_content(canned_payload, expected_count=len(data.products))
    result = check_language_match(data, content)
    assert result.passed


def test_language_match_fails_english_prose_vs_russian_input():
    data = make_input()  # Russian client/project/product name
    content = make_content(
        intro="This is a great faucet for your bathroom, built to last for years.",
        descriptions=["A reliable and durable mixer tap for everyday use in any home."],
        closing="Please reach out if you have any questions about this proposal.",
    )
    result = check_language_match(data, content)
    assert not result.passed
    assert isinstance(result, CheckResult)


def test_language_match_passes_when_both_english():
    data = make_input(
        client="Acme Interiors Ltd",
        project="Office kitchen, 12 m2",
        products=[Product(name="Stainless steel sink", price="100")],
    )
    content = make_content(
        intro="We are pleased to offer a curated selection for your office kitchen renovation.",
        descriptions=["A durable stainless steel sink built for daily office use."],
        closing="Let us know if you have any questions about this proposal.",
    )
    result = check_language_match(data, content)
    assert result.passed


# --- check_length_bounds -----------------------------------------------------


def test_length_bounds_passes_within_range(canned_payload):
    data = load_input(SAMPLE)
    content = validate_llm_content(canned_payload, expected_count=len(data.products))
    assert check_length_bounds(data, content).passed


def test_length_bounds_fails_on_five_char_intro():
    data = make_input()
    content = make_content(
        intro="Hi.",
        descriptions=["A solid, dependable mixer tap that is comfortable to use every day."],
        closing="Thank you for considering our proposal for your project, we look forward.",
    )
    result = check_length_bounds(data, content)
    assert not result.passed
    assert "intro" in result.detail


# --- check_no_invented_numbers -----------------------------------------------


def test_no_invented_numbers_passes_on_canned_fixture(canned_payload):
    data = load_input(SAMPLE)
    content = validate_llm_content(canned_payload, expected_count=len(data.products))
    assert check_no_invented_numbers(data, content).passed


def test_no_invented_numbers_fails_on_number_absent_from_any_name():
    data = make_input()
    content = make_content(descriptions=["This model has sold over 9999 units worldwide already."])
    result = check_no_invented_numbers(data, content)
    assert not result.passed
    assert "9999" in result.detail


def test_no_invented_numbers_passes_when_number_present_in_spec_token():
    data = make_input(
        products=[Product(name="Светильник потолочный влагозащищённый IP44", price="3400")]
    )
    content = make_content(
        descriptions=["Светильник с классом защиты 44 подходит для влажных помещений."]
    )
    result = check_no_invented_numbers(data, content)
    assert result.passed


def test_no_invented_numbers_fails_on_currency_symbol():
    data = make_input()
    content = make_content(descriptions=["This faucet is a great deal at only ₽500 today."])
    result = check_no_invented_numbers(data, content)
    assert not result.passed
    assert "₽" in result.detail


# --- check_no_markdown_artifacts ---------------------------------------------


def test_no_markdown_artifacts_passes_on_canned_fixture(canned_payload):
    data = load_input(SAMPLE)
    content = validate_llm_content(canned_payload, expected_count=len(data.products))
    assert check_no_markdown_artifacts(data, content).passed


@pytest.mark.parametrize(
    "text",
    [
        "Here is some prose\n```\ncode fence\n```\nmore prose",
        "This is **bold** and should not be here",
        "## A heading should not appear here either",
        "Some intro text\n* a bullet point that should not appear\nmore text",
    ],
)
def test_no_markdown_artifacts_fails_on_markdown(text):
    data = make_input()
    content = make_content(intro=text)
    result = check_no_markdown_artifacts(data, content)
    assert not result.passed
