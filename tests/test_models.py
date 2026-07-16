from decimal import Decimal
from pathlib import Path

import pytest

from proposal_gen.errors import InputError
from proposal_gen.models import ProposalInput, load_input


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "products.yaml"
    p.write_text(text, encoding="utf-8")
    return p


VALID = """\
client: "ООО «Ромашка»"
project: "Bathroom, 6 m²"
products:
  - name: "Grohe Eurosmart mixer"
    price: 8900
  - name: "Roca Gap wall-hung toilet"
    price: 21500.50
"""


def test_valid_input_parses_with_decimal_prices_and_total(tmp_path):
    data = load_input(write(tmp_path, VALID))
    assert isinstance(data, ProposalInput)
    assert data.client == "ООО «Ромашка»"
    assert [p.price for p in data.products] == [Decimal("8900"), Decimal("21500.50")]
    assert data.total == Decimal("30400.50")


def test_missing_file_raises_input_error(tmp_path):
    with pytest.raises(InputError, match="not found"):
        load_input(tmp_path / "nope.yaml")


def test_invalid_yaml_raises_input_error(tmp_path):
    with pytest.raises(InputError, match="Invalid YAML"):
        load_input(write(tmp_path, "client: [unclosed"))


def test_non_mapping_yaml_raises_input_error(tmp_path):
    with pytest.raises(InputError, match="mapping"):
        load_input(write(tmp_path, "- just\n- a list\n"))


@pytest.mark.parametrize(
    "text,fragment",
    [
        ("project: p\nproducts: [{name: n, price: 1}]\n", "client"),
        ("client: c\nproducts: [{name: n, price: 1}]\n", "project"),
        ("client: c\nproject: p\nproducts: []\n", "products"),
        ("client: c\nproject: p\nproducts: [{name: n}]\n", "price"),
        ("client: c\nproject: p\nproducts: [{name: n, price: -5}]\n", "price"),
        ("client: c\nproject: p\nproducts: [{name: n, price: 0}]\n", "price"),
        ("client: c\nproject: p\nproducts: [{name: n, price: abc}]\n", "price"),
        ("client: c\nproject: p\nproducts: [{name: '', price: 1}]\n", "name"),
        ("client: c\nproject: p\nproducts: [{name: n, price: 1, x: 1}]\n", "x"),
    ],
)
def test_schema_violations_raise_input_error(tmp_path, text, fragment):
    with pytest.raises(InputError, match=fragment):
        load_input(write(tmp_path, text))
