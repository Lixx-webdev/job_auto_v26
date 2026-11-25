from __future__ import annotations

from google import genai

from backend.config import get_settings

# Single place to change the model if Google renames/retires it.
MODEL = "gemini-3.5-flash-lite"          # resume parsing + job scoring (fast, ~2s)
WRITING_MODEL = "gemini-3.5-flash"       # cover letters (better prose, ~10s)


def get_client() -> genai.Client:
    """Gemini client using the key from .env (Settings), not the process environment."""
    return genai.Client(api_key=get_settings().GEMINI_API_KEY)
