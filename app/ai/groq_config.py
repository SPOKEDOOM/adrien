from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from app.ai.openai_config import load_optional_dotenv

DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
DEFAULT_GROQ_TIMEOUT_SECONDS = 30.0
DEFAULT_GROQ_MAX_OUTPUT_TOKENS = 700


def _boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in ("1", "true", "yes", "on"): return True
    if normalized in ("0", "false", "no", "off"): return False
    raise ValueError("Groq enabled setting must be true or false.")


@dataclass(frozen=True, slots=True)
class GroqConfig:
    api_key_present: bool
    model: str = DEFAULT_GROQ_MODEL
    timeout_seconds: float = DEFAULT_GROQ_TIMEOUT_SECONDS
    max_output_tokens: int = DEFAULT_GROQ_MAX_OUTPUT_TOKENS
    enabled: bool = True
    api_key: str = field(default="", repr=False, compare=False)
    environment_detected: bool = False

    def __post_init__(self):
        if not self.model.strip(): raise ValueError("Groq model must be non-empty.")
        if self.timeout_seconds <= 0: raise ValueError("Groq timeout must be positive.")
        if self.max_output_tokens <= 0: raise ValueError("Groq max output tokens must be positive.")

    @classmethod
    def from_environment(cls, *, dotenv_values=None, enabled: bool | None = None):
        dotenv_values = dotenv_values or {}
        api_key = (os.getenv("GROQ_API_KEY") or "").strip()
        dotenv_key = (dotenv_values.get("GROQ_API_KEY") or "").strip()
        resolved_key = api_key or dotenv_key

        def value(name, default):
            return ((os.getenv(name) or "").strip() or
                    (dotenv_values.get(name) or "").strip() or default)
        try:
            timeout = float(value("ADRIEN_GROQ_TIMEOUT_SECONDS", str(DEFAULT_GROQ_TIMEOUT_SECONDS)))
            tokens = int(value("ADRIEN_GROQ_MAX_OUTPUT_TOKENS", str(DEFAULT_GROQ_MAX_OUTPUT_TOKENS)))
            resolved_enabled = _boolean(value("ADRIEN_GROQ_ENABLED", "true")) if enabled is None else bool(enabled)
        except ValueError as exc:
            raise ValueError(f"Invalid Groq configuration: {exc}") from exc
        return cls(bool(resolved_key), value("ADRIEN_GROQ_MODEL", DEFAULT_GROQ_MODEL),
                   timeout, tokens, resolved_enabled, resolved_key, bool(api_key))

    @classmethod
    def resolve(cls, *, dotenv_path: str | Path = ".env", enabled: bool | None = None):
        return cls.from_environment(dotenv_values=load_optional_dotenv(dotenv_path), enabled=enabled)
