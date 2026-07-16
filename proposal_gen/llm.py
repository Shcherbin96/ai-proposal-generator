"""LLM provider boundary.

The provider receives product NAMES only — never prices — and returns prose.
Anything numeric in the final document comes from the input file (models.py).
The provider is a Protocol, so any OpenAI-compatible endpoint (Gemini, OpenAI,
Ollama, vLLM) or a test double plugs in without touching business logic.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Protocol

from openai import OpenAI, OpenAIError

from proposal_gen.config import Settings
from proposal_gen.errors import LLMError
from proposal_gen.models import LLMContent, ProposalInput, validate_llm_content

logger = logging.getLogger(__name__)

# Bump this on any change to PROMPT_TEMPLATE's wording or structure — it is
# logged with every call so prompt regressions can be correlated after the fact.
PROMPT_VERSION = "1"

PROMPT_TEMPLATE = """\
You are a sales manager at "{seller}" ({tagline}). Write the prose for a commercial proposal.

Client: {client}. Project: {project}.
Products (numbered, keep this order):
{products}

Write in the same language as the client and product names above.

Rules:
- intro: a short opening, 2-3 sentences, to the point, no fluff.
- For EVERY product: 1-2 sentences on its benefit. Do NOT invent technical
  specs or numbers you don't know; write about usefulness, quality, convenience.
- closing: a short close with a soft call to action.
- Do not mention prices or amounts; pricing is handled separately.

Return STRICT JSON, no markdown:
{{"intro": "...", "items": [{{"index": 0, "description": "..."}}, ...], "closing": "..."}}
Include every product index from 0 to {last_index} exactly once, in order."""
# NOTE: when json_mode is on, the OpenAI-compatible `response_format={"type":
# "json_object"}` param REQUIRES the literal word "json" to appear somewhere
# in the prompt (the line above satisfies it) — do not "clean up" that
# phrasing away, it would break JSON mode at the API level, not just in spirit.


def build_prompt(data: ProposalInput, seller_name: str, seller_tagline: str) -> str:
    products = "\n".join(f"{i}. {p.name}" for i, p in enumerate(data.products))
    return PROMPT_TEMPLATE.format(
        seller=seller_name,
        tagline=seller_tagline,
        client=data.client,
        project=data.project,
        products=products,
        last_index=len(data.products) - 1,
    )


class LLMProvider(Protocol):
    def complete(self, prompt: str) -> str:
        """Return the raw text of the model's reply."""
        ...


class OpenAICompatProvider:
    """Any OpenAI-compatible endpoint. Timeouts and retries via the openai SDK."""

    def __init__(self, settings: Settings) -> None:
        self._model = settings.model
        self._temperature = settings.temperature
        self._json_mode = settings.json_mode
        self._client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.timeout_s,
            max_retries=settings.max_retries,
        )

    def complete(self, prompt: str) -> str:
        start = time.perf_counter()
        try:
            if self._json_mode:
                # Verified live against Gemini's OpenAI-compat endpoint:
                # accepted, and it returns real resp.usage. strip_code_fence
                # below stays untouched as graceful degradation for endpoints
                # without JSON mode.
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self._temperature,
                    response_format={"type": "json_object"},
                )
            else:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self._temperature,
                )
        except OpenAIError as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        if not resp.choices:
            raise LLMError("LLM returned no choices")
        content = resp.choices[0].message.content
        if not content:
            raise LLMError("LLM returned an empty completion")

        latency_ms = int((time.perf_counter() - start) * 1000)
        # resp.usage is None on some OpenAI-compatible endpoints that don't
        # report token counts — degrade to "n/a" rather than crash a
        # successful call over an observability nicety.
        usage = resp.usage
        prompt_tokens: int | str
        completion_tokens: int | str
        total_tokens: int | str
        if usage is None:
            prompt_tokens = completion_tokens = total_tokens = "n/a"
        else:
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens
        logger.info(
            "LLM call: model=%s prompt_version=%s latency_ms=%d tokens=%s/%s/%s",
            self._model,
            PROMPT_VERSION,
            latency_ms,
            prompt_tokens,
            completion_tokens,
            total_tokens,
        )
        return content


def strip_code_fence(text: str) -> str:
    """Unwrap ```json ... ``` fences some models add despite instructions."""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) < 3:
            raise LLMError("Unclosed markdown code fence in LLM response")
        text = parts[1].removeprefix("json").strip()
    return text


def request_content(provider: LLMProvider, prompt: str, expected_count: int) -> LLMContent:
    """One provider round-trip: complete -> parse JSON -> validate the contract."""
    raw_text = provider.complete(prompt)
    logger.debug("LLM raw response: %d chars", len(raw_text))
    try:
        raw = json.loads(strip_code_fence(raw_text))
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM response is not valid JSON: {exc}") from exc
    return validate_llm_content(raw, expected_count)
