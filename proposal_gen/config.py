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


def _float_env(name: str, default: str) -> float:
    raw = os.getenv(name, default)
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


def _int_env(name: str, default: str) -> int:
    raw = os.getenv(name, default)
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


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
        base_url=os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL),
        model=os.getenv("LLM_MODEL", DEFAULT_MODEL),
        timeout_s=_float_env("LLM_TIMEOUT_S", "60"),
        max_retries=_int_env("LLM_MAX_RETRIES", "2"),
    )
