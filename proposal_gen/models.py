"""Validated domain models for proposal input and generated copy."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

import yaml

from proposal_gen.errors import InputValidationError, LLMResponseError


@dataclass(frozen=True, slots=True)
class Product:
    """One deterministic line item from the source data."""

    name: str
    price: Decimal


@dataclass(frozen=True, slots=True)
class ProposalData:
    """Validated proposal request loaded from YAML."""

    client: str
    project: str
    products: tuple[Product, ...]

    @property
    def total(self) -> Decimal:
        return sum((product.price for product in self.products), start=Decimal("0"))


@dataclass(frozen=True, slots=True)
class GeneratedCopy:
    """Validated prose returned by the LLM."""

    intro: str
    descriptions: tuple[str, ...]
    closing: str


def _non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputValidationError(f"'{field}' must be a non-empty string.")
    return value.strip()


def _price(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise InputValidationError(f"'{field}' must be a non-negative number.")

    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise InputValidationError(f"'{field}' must be a non-negative number.") from exc

    if not parsed.is_finite() or parsed < 0:
        raise InputValidationError(f"'{field}' must be a finite, non-negative number.")
    return parsed


def load_proposal_data(path: str | Path) -> ProposalData:
    """Load and validate the YAML input contract."""

    source = Path(path)
    try:
        with source.open(encoding="utf-8") as stream:
            raw = yaml.safe_load(stream)
    except FileNotFoundError as exc:
        raise InputValidationError(f"Input file not found: {source}") from exc
    except OSError as exc:
        raise InputValidationError(f"Could not read input file: {source}") from exc
    except yaml.YAMLError as exc:
        raise InputValidationError(f"Input file contains invalid YAML: {source}") from exc

    if not isinstance(raw, Mapping):
        raise InputValidationError("Input root must be a YAML mapping.")

    client = _non_empty_text(raw.get("client"), "client")
    project = _non_empty_text(raw.get("project"), "project")
    raw_products = raw.get("products")
    if not isinstance(raw_products, list) or not raw_products:
        raise InputValidationError("'products' must be a non-empty list.")

    products: list[Product] = []
    for index, raw_product in enumerate(raw_products, start=1):
        if not isinstance(raw_product, Mapping):
            raise InputValidationError(f"'products[{index}]' must be a mapping.")
        products.append(
            Product(
                name=_non_empty_text(raw_product.get("name"), f"products[{index}].name"),
                price=_price(raw_product.get("price"), f"products[{index}].price"),
            )
        )

    return ProposalData(client=client, project=project, products=tuple(products))


def _generated_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LLMResponseError(f"LLM field '{field}' must be a non-empty string.")
    return value.strip()


def parse_generated_copy(payload: Any, expected_items: int) -> GeneratedCopy:
    """Validate the structured LLM response before using any prose."""

    if not isinstance(payload, Mapping):
        raise LLMResponseError("LLM response must be a JSON object.")

    intro = _generated_text(payload.get("intro"), "intro")
    closing = _generated_text(payload.get("closing"), "closing")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise LLMResponseError("LLM field 'items' must be a list.")
    if len(raw_items) != expected_items:
        raise LLMResponseError(
            f"LLM returned {len(raw_items)} item descriptions; expected {expected_items}."
        )

    descriptions: list[str] = []
    for expected_index, raw_item in enumerate(raw_items, start=1):
        if not isinstance(raw_item, Mapping):
            raise LLMResponseError(f"LLM item {expected_index} must be a JSON object.")
        item_index = raw_item.get("index")
        if isinstance(item_index, bool) or item_index != expected_index:
            raise LLMResponseError(
                f"LLM item order mismatch: expected index {expected_index}, got {item_index!r}."
            )
        descriptions.append(
            _generated_text(raw_item.get("description"), f"items[{expected_index}].description")
        )

    return GeneratedCopy(
        intro=intro,
        descriptions=tuple(descriptions),
        closing=closing,
    )
