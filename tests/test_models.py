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


def test_non_utf8_file_raises_input_error(tmp_path):
    p = tmp_path / "p.yaml"
    p.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(InputError, match="UTF-8"):
        load_input(p)


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
        ("client: c\nproject: p\nproducts: [{name: n, price: .nan}]\n", "price"),
        ("client: c\nproject: p\nproducts: [{name: n, price: .inf}]\n", "price"),
        ("client: c\nproject: p\nproducts: [{name: n, price: true}]\n", "price"),
        ("client: c\nproject: p\nproducts: [{name: n, price: 10.005}]\n", "price"),
    ],
)
def test_schema_violations_raise_input_error(tmp_path, text, fragment):
    with pytest.raises(InputError, match=fragment):
        load_input(write(tmp_path, text))


WITH_SELLER = """\
client: "Client"
project: "Project"
products:
  - name: "Widget"
    price: 100
seller:
  name: "Custom Seller Co"
  tagline: "Custom tagline"
  contacts: "custom@example.com"
"""


def test_seller_override_parses_when_present(tmp_path):
    data = load_input(write(tmp_path, WITH_SELLER))
    assert data.seller is not None
    assert data.seller.name == "Custom Seller Co"
    assert data.seller.tagline == "Custom tagline"
    assert data.seller.contacts == "custom@example.com"


def test_seller_is_none_when_absent(tmp_path):
    data = load_input(write(tmp_path, VALID))
    assert data.seller is None


def test_seller_with_empty_name_raises_input_error(tmp_path):
    text = WITH_SELLER.replace('name: "Custom Seller Co"', 'name: ""')
    with pytest.raises(InputError, match="seller"):
        load_input(write(tmp_path, text))


def test_seller_with_unknown_key_raises_input_error(tmp_path):
    text = WITH_SELLER.replace(
        'contacts: "custom@example.com"', 'contacts: "custom@example.com"\n  x: "surprise"'
    )
    with pytest.raises(InputError, match="x"):
        load_input(write(tmp_path, text))
