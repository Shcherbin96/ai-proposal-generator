from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from proposal_gen.generate import _decode_llm_json, generate, render_html
from proposal_gen.models import GeneratedCopy, Product, ProposalData


class RenderingTests(TestCase):
    def test_escapes_untrusted_input_and_llm_copy(self) -> None:
        data = ProposalData(
            client="<script>alert(1)</script>",
            project="Demo",
            products=(Product(name="<b>Desk</b>", price=Decimal("1000")),),
        )
        generated = GeneratedCopy(
            intro="<img src=x onerror=alert(1)>",
            descriptions=("<em>Useful</em>",),
            closing="Done",
        )

        html = render_html(data, generated, generated_on=date(2026, 7, 16))

        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_decodes_json_inside_markdown_fence(self) -> None:
        payload = _decode_llm_json('```json\n{"intro":"A","items":[],"closing":"B"}\n```')
        self.assertEqual(payload["intro"], "A")


class PipelineTests(TestCase):
    def test_generates_without_real_provider_or_browser(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "input.yaml"
            output_path = root / "proposal.pdf"
            input_path.write_text(
                """client: Example Client
project: Office fit-out
products:
  - name: Desk
    price: 1000
  - name: Lamp
    price: 250
""",
                encoding="utf-8",
            )
            captured_html: list[str] = []

            def fake_llm(_: str) -> dict:
                return {
                    "intro": "Intro",
                    "items": [
                        {"index": 1, "description": "Desk benefit"},
                        {"index": 2, "description": "Lamp benefit"},
                    ],
                    "closing": "Closing",
                }

            def fake_renderer(html: str, destination: Path) -> None:
                captured_html.append(html)
                destination.write_bytes(b"%PDF-test")

            result = generate(
                input_path,
                output_path,
                llm_call=fake_llm,
                pdf_renderer=fake_renderer,
            )

            self.assertEqual(result, output_path)
            self.assertTrue(output_path.exists())
            self.assertIn("1 250", captured_html[0])
            self.assertIn("Desk benefit", captured_html[0])
