"""Prose quality checks for generated proposal content.

Pure functions over (ProposalInput, LLMContent) — no I/O, no network. These
run in CI against fixtures (tests/test_eval_checks.py) and are reused by the
live eval runner (scripts/run_evals.py) against real LLM output.

Design constraints (deliberate, see Phase 2 plan):
- Zero new dependencies. The language check is a Cyrillic-ratio heuristic,
  not a language-detection library.
- The "no invented numbers" check whitelists digit/spec tokens that already
  appear in the input product names (IP44, 80x60, model numbers, etc. are
  legitimate to echo back in prose).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from proposal_gen.models import LLMContent, ProposalInput

# --- check_length_bounds: approximations of PROMPT_TEMPLATE's sentence rules
# (llm.py) in characters. Generous enough to allow normal sentence-length
# variance, tight enough to catch a truncated or run-on reply.
INTRO_MIN_CHARS = 40
INTRO_MAX_CHARS = 400
DESCRIPTION_MIN_CHARS = 30
DESCRIPTION_MAX_CHARS = 300
CLOSING_MIN_CHARS = 30
CLOSING_MAX_CHARS = 300

# --- check_language_match: how far the prose's Cyrillic ratio may drift from
# the input's before we call it a language mismatch.
LANGUAGE_RATIO_DELTA = 0.35

# --- check_no_invented_numbers: currency symbols are never legitimate in
# prose — the prompt says pricing is handled separately, so any of these
# characters means the model leaked a price into the text regardless of the
# whitelist.
CURRENCY_CHARS = "₽$€"

_DIGIT_RUN_RE = re.compile(r"\d+")
_EDGE_NON_WORD_RE = re.compile(r"^\W+|\W+$", re.UNICODE)


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str  # human-readable, e.g. "intro cyrillic ratio 0.82 vs input 0.82"


def _cyrillic_ratio(text: str) -> float:
    """Cyrillic letters / all letters in text. No letters at all -> 0.0."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    cyrillic = sum(1 for ch in letters if "Ѐ" <= ch <= "ӿ")
    return cyrillic / len(letters)


def check_language_match(data: ProposalInput, content: LLMContent) -> CheckResult:
    """The prose's script should match the input's script.

    Pass if the Cyrillic ratios are within LANGUAGE_RATIO_DELTA of each other,
    OR both are on the same side of 0.5 (both majority-Cyrillic, or both
    majority-Latin) — a simple, explainable rule rather than a language
    detector.
    """
    descriptions = (item.description for item in content.items)
    prose = " ".join([content.intro, *descriptions, content.closing])
    input_text = " ".join([data.client, data.project, *(p.name for p in data.products)])
    prose_ratio = _cyrillic_ratio(prose)
    input_ratio = _cyrillic_ratio(input_text)
    delta = abs(prose_ratio - input_ratio)
    same_side = (prose_ratio >= 0.5) == (input_ratio >= 0.5)
    passed = delta <= LANGUAGE_RATIO_DELTA or same_side
    detail = (
        f"prose cyrillic ratio {prose_ratio:.2f} vs input cyrillic ratio {input_ratio:.2f} "
        f"(delta {delta:.2f}, same_side={same_side})"
    )
    return CheckResult("language_match", passed, detail)


def check_length_bounds(data: ProposalInput, content: LLMContent) -> CheckResult:
    """intro/description/closing lengths must fall within the module-level bounds."""
    problems = []
    if not (INTRO_MIN_CHARS <= len(content.intro) <= INTRO_MAX_CHARS):
        problems.append(
            f"intro is {len(content.intro)} chars (want {INTRO_MIN_CHARS}-{INTRO_MAX_CHARS})"
        )
    for item in content.items:
        n = len(item.description)
        if not (DESCRIPTION_MIN_CHARS <= n <= DESCRIPTION_MAX_CHARS):
            problems.append(
                f"item {item.index} description is {n} chars "
                f"(want {DESCRIPTION_MIN_CHARS}-{DESCRIPTION_MAX_CHARS})"
            )
    if not (CLOSING_MIN_CHARS <= len(content.closing) <= CLOSING_MAX_CHARS):
        problems.append(
            f"closing is {len(content.closing)} chars "
            f"(want {CLOSING_MIN_CHARS}-{CLOSING_MAX_CHARS})"
        )
    passed = not problems
    detail = "all sections within bounds" if passed else "; ".join(problems)
    return CheckResult("length_bounds", passed, detail)


def _normalize_token(token: str) -> str:
    """Strip leading/trailing non-word characters, casefold. Keeps internal
    punctuation like the x in "80x60" intact."""
    return _EDGE_NON_WORD_RE.sub("", token).casefold()


def _build_number_whitelist(data: ProposalInput) -> set[str]:
    """Digit-bearing tokens and bare digit-runs from everything the model is
    actually told (client, project, product names — see llm.py:build_prompt;
    only prices are withheld). This mirrors check_language_match's definition
    of "the input": a model faithfully echoing a known fact, e.g. the
    project's area in square meters ("6 m2"), is not "inventing" a number —
    it's reflecting text it was given. Product names are still the dominant
    source of legitimate spec tokens (IP44, 80x60, model numbers).

    Two sources, unioned, per text field:
    - whole whitespace-split tokens that contain a digit, normalized (e.g.
      "80x60" or "ip44");
    - individual digit-runs found anywhere in the text via regex, so "80x60"
      also contributes "80" and "60", and "IP44" contributes "44".
    Only the digit-run entries are actually consulted when scanning prose
    (prose is scanned for bare digit-runs too), but both are built here per
    the agreed design.
    """
    texts = [data.client, data.project, *(p.name for p in data.products)]
    whitelist: set[str] = set()
    for text in texts:
        for token in text.split():
            normalized = _normalize_token(token)
            if normalized and any(ch.isdigit() for ch in normalized):
                whitelist.add(normalized)
        whitelist.update(_DIGIT_RUN_RE.findall(text))
    return whitelist


def check_no_invented_numbers(data: ProposalInput, content: LLMContent) -> CheckResult:
    """Every digit-run in the prose must trace back to a product name; no
    currency symbols are allowed in prose at all."""
    prose_parts = [content.intro, *(item.description for item in content.items), content.closing]
    prose = "\n".join(prose_parts)

    problems = []
    currency_found = sorted({ch for ch in prose if ch in CURRENCY_CHARS})
    if currency_found:
        problems.append(f"currency symbols in prose: {', '.join(currency_found)}")

    whitelist = _build_number_whitelist(data)
    found_runs = _DIGIT_RUN_RE.findall(prose)
    invented = list(dict.fromkeys(run for run in found_runs if run not in whitelist))
    if invented:
        problems.append(f"numbers not found in any product name: {invented}")

    passed = not problems
    if passed:
        detail = f"no invented numbers or currency symbols (whitelist: {sorted(whitelist)})"
    else:
        detail = "; ".join(problems)
    return CheckResult("no_invented_numbers", passed, detail)


def check_no_markdown_artifacts(data: ProposalInput, content: LLMContent) -> CheckResult:
    """Prose is plain text for an HTML template — no markdown fences, bold,
    headings, or bullet lines should leak through from the model's reply."""
    sections = {"intro": content.intro, "closing": content.closing}
    for item in content.items:
        sections[f"item {item.index} description"] = item.description

    problems = []
    for name, text in sections.items():
        if "```" in text:
            problems.append(f"{name}: contains a code fence (```)")
        if "**" in text:
            problems.append(f"{name}: contains a bold marker (**)")
        if "##" in text:
            problems.append(f"{name}: contains a heading marker (##)")
        if any(line.lstrip().startswith("* ") for line in text.splitlines()):
            problems.append(f"{name}: contains a bullet line ('* ' at line start)")

    passed = not problems
    detail = "no markdown artifacts found" if passed else "; ".join(problems)
    return CheckResult("no_markdown_artifacts", passed, detail)


def run_all_checks(data: ProposalInput, content: LLMContent) -> list[CheckResult]:
    return [
        check_language_match(data, content),
        check_length_bounds(data, content),
        check_no_invented_numbers(data, content),
        check_no_markdown_artifacts(data, content),
    ]
