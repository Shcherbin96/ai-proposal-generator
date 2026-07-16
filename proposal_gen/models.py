"""Data contracts for both sides of the LLM boundary.

Boundary rule of this project: every number in the final document (prices,
total) comes from the input file and is computed in Python. The LLM
contributes prose only, matched to products by explicit index. Both sides
are enforced here with strict pydantic models.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from proposal_gen.errors import InputError, LLMError


def _format_errors(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()
    )


class Product(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    price: Decimal = Field(gt=0)


class ProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    client: str = Field(min_length=1)
    project: str = Field(min_length=1)
    products: list[Product] = Field(min_length=1)

    @property
    def total(self) -> Decimal:
        """The one and only source of the total — never the LLM."""
        return sum((p.price for p in self.products), Decimal(0))


def load_input(path: Path) -> ProposalInput:
    """Load and validate the products file; raise InputError with a readable message."""
    if not path.is_file():
        raise InputError(f"Input file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise InputError(f"Invalid YAML in {path}: {exc}") from exc
    except OSError as exc:
        raise InputError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise InputError(f"{path}: expected a YAML mapping with client, project, products")
    try:
        return ProposalInput.model_validate(raw)
    except ValidationError as exc:
        raise InputError(f"{path}: {_format_errors(exc)}") from exc


class LLMItem(BaseModel):
    """One product description. Matched to a product by index, never by name."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    index: int = Field(ge=0)
    description: str = Field(min_length=1)


class LLMContent(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    intro: str = Field(min_length=1)
    items: list[LLMItem]
    closing: str = Field(min_length=1)


def validate_llm_content(raw: object, expected_count: int) -> LLMContent:
    """Accept only a response that covers every product exactly once, in order."""
    try:
        content = LLMContent.model_validate(raw)
    except ValidationError as exc:
        raise LLMError(f"LLM response failed validation: {_format_errors(exc)}") from exc
    indices = [item.index for item in content.items]
    if indices != list(range(expected_count)):
        raise LLMError(
            f"LLM response must describe all {expected_count} products in order; "
            f"got indices {indices}"
        )
    return content
