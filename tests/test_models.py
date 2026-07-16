from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from proposal_gen.errors import InputValidationError, LLMResponseError
from proposal_gen.models import load_proposal_data, parse_generated_copy


class ProposalInputTests(TestCase):
    def _write(self, content: str) -> Path:
        self.temp_dir = TemporaryDirectory()
        path = Path(self.temp_dir.name) / "proposal.yaml"
        path.write_text(content, encoding="utf-8")
        self.addCleanup(self.temp_dir.cleanup)
        return path

    def test_loads_valid_yaml_and_calculates_total(self) -> None:
        path = self._write(
            """client: Example Client
project: Office fit-out
products:
  - name: Desk
    price: 1000
  - name: Lamp
    price: 250.50
"""
        )

        data = load_proposal_data(path)

        self.assertEqual(data.client, "Example Client")
        self.assertEqual(len(data.products), 2)
        self.assertEqual(data.total, Decimal("1250.50"))

    def test_rejects_empty_product_list(self) -> None:
        path = self._write(
            """client: Example Client
project: Office fit-out
products: []
"""
        )

        with self.assertRaisesRegex(InputValidationError, "non-empty list"):
            load_proposal_data(path)

    def test_rejects_boolean_price(self) -> None:
        path = self._write(
            """client: Example Client
project: Office fit-out
products:
  - name: Desk
    price: true
"""
        )

        with self.assertRaisesRegex(InputValidationError, "non-negative number"):
            load_proposal_data(path)


class GeneratedCopyTests(TestCase):
    def test_accepts_exact_indexed_items(self) -> None:
        generated = parse_generated_copy(
            {
                "intro": "Intro",
                "items": [
                    {"index": 1, "description": "First"},
                    {"index": 2, "description": "Second"},
                ],
                "closing": "Closing",
            },
            expected_items=2,
        )

        self.assertEqual(generated.descriptions, ("First", "Second"))

    def test_rejects_missing_item_instead_of_silent_truncation(self) -> None:
        with self.assertRaisesRegex(LLMResponseError, "expected 2"):
            parse_generated_copy(
                {
                    "intro": "Intro",
                    "items": [{"index": 1, "description": "Only one"}],
                    "closing": "Closing",
                },
                expected_items=2,
            )

    def test_rejects_item_order_mismatch(self) -> None:
        with self.assertRaisesRegex(LLMResponseError, "order mismatch"):
            parse_generated_copy(
                {
                    "intro": "Intro",
                    "items": [{"index": 2, "description": "Wrong index"}],
                    "closing": "Closing",
                },
                expected_items=1,
            )
