"""Настройки в одном месте."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# LLM (Gemini через OpenAI-совместимый эндпоинт — provider-agnostic)
LLM_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
MODEL = "gemini-2.5-flash-lite"

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = ROOT / "output"

# Компания-продавец (демо). Меняется под себя.
SELLER = {
    "name": "ИнтерьерПро",
    "tagline": "Комплектация интерьеров под ключ",
    "contacts": "+7 999 000-00-00 · hello@interiorpro.example",
}
