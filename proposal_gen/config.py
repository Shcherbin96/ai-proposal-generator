"""Local configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = ROOT / "output"

LLM_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta/openai/",
).strip()
MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash-lite").strip()
LLM_TIMEOUT_SECONDS = 30.0
LLM_MAX_RETRIES = 2

SELLER = {
    "name": "ИнтерьерПро",
    "tagline": "Комплектация интерьеров под ключ",
    "contacts": "+7 999 000-00-00 · hello@interiorpro.example",
}
