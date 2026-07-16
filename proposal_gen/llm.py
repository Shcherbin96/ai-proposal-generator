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
        except LLMError as exc:
            # A failed call must be observable too: without this, a hanging or
            # erroring provider leaves no latency trail. LLMError messages are
            # short and contain no raw reply and no credentials.
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "LLM call FAILED: model=%s prompt_version=%s latency_ms=%d error=%s",
                self._model,
                PROMPT_VERSION,
                latency_ms,
                exc,
            )
            raise

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


# Cap on how much of a bad reply gets embedded back into the repair prompt.
# A pathologically long reply (or a runaway/adversarial one) would otherwise
# double token spend on retry for no additional diagnostic value — the error
# message already says what's wrong; the model doesn't need the whole thing back.
_BAD_REPLY_CAP = 4000

REPAIR_TEMPLATE = (
    "{prompt}\n\n"
    "Your previous reply was rejected:\n{bad_reply}\n\n"
    "Validation error: {error}\n\n"
    "Return ONLY the corrected strict JSON object, nothing else."
)


def _parse_and_validate(raw_text: str, expected_count: int) -> LLMContent:
    """Parse + contract-check one reply. Raises LLMError — the repairable class."""
    try:
        raw = json.loads(strip_code_fence(raw_text))
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM response is not valid JSON: {exc}") from exc
    return validate_llm_content(raw, expected_count)


def request_content(
    provider: LLMProvider, prompt: str, expected_count: int, max_repairs: int = 1
) -> LLMContent:
    """One or more provider round-trips: complete -> parse JSON -> validate.

    On a repairable failure (invalid JSON, an unclosed fence, or a contract
    violation from validate_llm_content), the validation error is fed back to
    the model and the call retried, up to max_repairs times. Transport errors
    raised by provider.complete() itself are a different failure class —
    they are NOT caught here and propagate immediately; the SDK already
    retries those (LLM_MAX_RETRIES), so retrying them again here would be
    redundant and would blur two distinct knobs into one.
    """
    current_prompt = prompt
    attempt = 0
    while True:
        raw_text = provider.complete(current_prompt)  # transport errors: not caught, propagate
        logger.debug("LLM raw response: %d chars", len(raw_text))
        try:
            return _parse_and_validate(raw_text, expected_count)
        except LLMError as exc:
            attempt += 1
            if attempt > max_repairs:
                raise
            logger.warning(
                "LLM reply failed validation (attempt %d/%d): %s — requesting repair",
                attempt,
                max_repairs,
                exc,
            )
            current_prompt = REPAIR_TEMPLATE.format(
                prompt=prompt,
                bad_reply=raw_text[:_BAD_REPLY_CAP],
                error=exc,
            )
