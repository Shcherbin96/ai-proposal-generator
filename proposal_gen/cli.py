"""Command-line entry point: human-readable errors, meaningful exit codes."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from proposal_gen import config
from proposal_gen.errors import ProposalError
from proposal_gen.generate import generate
from proposal_gen.llm import OpenAICompatProvider


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="proposal-gen",
        description="Generate a branded commercial proposal PDF from a product list.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=str(config.DATA / "products.yaml"),
        help="path to the products YAML file (default: data/products.yaml)",
    )
    parser.add_argument("-o", "--output", default=None, help="output PDF path")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        stream=sys.stderr,
        # force: basicConfig is a no-op once the root logger has handlers, so
        # without it a second main() call in one process would ignore -v.
        force=True,
    )

    try:
        settings = config.load_settings()
        provider = OpenAICompatProvider(settings)
        pdf = generate(Path(args.input), provider, Path(args.output) if args.output else None)
    except ProposalError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return exc.exit_code
    print(f"Proposal ready: {pdf}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
