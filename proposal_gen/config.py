"""Runtime configuration. Provider-neutral: any OpenAI-compatible endpoint works.

Secrets live in the environment (or .env); the API key is excluded from repr
so it can never leak through logs or tracebacks that print Settings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from proposal_gen.errors import ConfigError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = ROOT / "output"
TEMPLATE = Path(__file__).with_name("template.html")

# Defaults target Google Gemini's OpenAI-compatible endpoint; override
# LLM_BASE_URL / LLM_MODEL to use OpenAI, Ollama, vLLM or anything compatible.
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-2.5-flash-lite"

# Demo seller branding. Replace with your business.
SELLER = {
    "name": "ИнтерьерПро",
    "tagline": "Комплектация интерьеров под ключ",
    "contacts": "+7 999 000-00-00 · hello@interiorpro.example",
}


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout_s: float = 60.0
    max_retries: int = 2
    temperature: float = 0.4
    # No max_tokens setting: a low cap would truncate JSON mid-object, which
    # would manufacture exactly the failure the repair loop (Task 4) exists to
    # fix. Considered and rejected — let responses run to natural completion.
    json_mode: bool = True


def _positive_float_env(name: str, default: str) -> float:
    raw = os.getenv(name, default)
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc
    if value <= 0:
        raise ConfigError(f"{name} must be positive, got {raw!r}")
    return value


def _non_negative_int_env(name: str, default: str) -> int:
    raw = os.getenv(name, default)
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc
    if value < 0:
        raise ConfigError(f"{name} must be non-negative, got {raw!r}")
    return value


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _bool_env(name: str, default: str) -> bool:
    raw = os.getenv(name, default)
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ConfigError(f"{name} must be one of true/false (1/0, yes/no, on/off), got {raw!r}")


def _bounded_float_env(name: str, default: str, lo: float, hi: float) -> float:
    """Like _positive_float_env but allows the boundaries themselves (e.g. 0)."""
    raw = os.getenv(name, default)
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc
    if not (lo <= value <= hi):
        raise ConfigError(f"{name} must be between {lo} and {hi}, got {raw!r}")
    return value


def load_settings() -> Settings:
    load_dotenv()  # does not override variables already set in the environment
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        raise ConfigError(
            "LLM_API_KEY is not set. Copy .env.example to .env and add your key "
            "(any OpenAI-compatible provider works; defaults target Google Gemini)."
        )
    return Settings(
        api_key=api_key,
        # `or DEFAULT`: getenv defaults apply only when unset; treat an empty
        # string (e.g. a blank line in .env) the same as unset.
        base_url=os.getenv("LLM_BASE_URL", "").strip() or DEFAULT_BASE_URL,
        model=os.getenv("LLM_MODEL", "").strip() or DEFAULT_MODEL,
        timeout_s=_positive_float_env("LLM_TIMEOUT_S", "60"),
        max_retries=_non_negative_int_env("LLM_MAX_RETRIES", "2"),
        temperature=_bounded_float_env("LLM_TEMPERATURE", "0.4", 0.0, 2.0),
        json_mode=_bool_env("LLM_JSON_MODE", "true"),
    )
