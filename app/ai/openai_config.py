from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_OPENAI_MODEL = "gpt-5.6-sol"
DEFAULT_OPENAI_TIMEOUT_SECONDS = 30.0
DEFAULT_OPENAI_MAX_OUTPUT_TOKENS = 700


def load_optional_dotenv(path: str | Path = ".env") -> dict[str, str]:
    """Read supported .env values without mutating or overriding the runtime environment."""
    source = Path(path)
    if not source.is_file():
        return {}
    supported = {
        "OPENAI_API_KEY", "ADRIEN_OPENAI_MODEL", "ADRIEN_OPENAI_TIMEOUT_SECONDS",
        "ADRIEN_OPENAI_MAX_OUTPUT_TOKENS",
        "GROQ_API_KEY", "ADRIEN_GROQ_MODEL", "ADRIEN_GROQ_TIMEOUT_SECONDS",
        "ADRIEN_GROQ_MAX_OUTPUT_TOKENS", "ADRIEN_GROQ_ENABLED",
    }
    values: dict[str, str] = {}
    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name not in supported:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1].strip()
        values[name] = value
    return values


@dataclass(frozen=True, slots=True)
class OpenAIConfig:
    """Resolved OpenAI settings. The secret is excluded from repr and diagnostics."""

    api_key_present: bool
    model: str = DEFAULT_OPENAI_MODEL
    timeout_seconds: float = DEFAULT_OPENAI_TIMEOUT_SECONDS
    max_output_tokens: int = DEFAULT_OPENAI_MAX_OUTPUT_TOKENS
    enabled: bool = True
    api_key: str = field(default="", repr=False, compare=False)
    environment_detected: bool = False

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("OpenAI model must be non-empty.")
        if self.timeout_seconds <= 0:
            raise ValueError("OpenAI timeout must be positive.")
        if self.max_output_tokens <= 0:
            raise ValueError("OpenAI max output tokens must be positive.")

    @classmethod
    def from_environment(cls, *, enabled: bool = True, dotenv_values: dict[str, str] | None = None,
                         default_model: str = DEFAULT_OPENAI_MODEL) -> "OpenAIConfig":
        dotenv_values = dotenv_values or {}
        # Runtime environment always wins, including over an empty .env entry.
        environment_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        dotenv_key = (dotenv_values.get("OPENAI_API_KEY") or "").strip()
        api_key = environment_key or dotenv_key

        def resolved(name: str, default: str) -> str:
            environment_value = (os.getenv(name) or "").strip()
            dotenv_value = (dotenv_values.get(name) or "").strip()
            return environment_value or dotenv_value or default

        model = resolved("ADRIEN_OPENAI_MODEL", default_model)
        try:
            timeout = float(resolved("ADRIEN_OPENAI_TIMEOUT_SECONDS",
                                     str(DEFAULT_OPENAI_TIMEOUT_SECONDS)))
            max_tokens = int(resolved("ADRIEN_OPENAI_MAX_OUTPUT_TOKENS",
                                      str(DEFAULT_OPENAI_MAX_OUTPUT_TOKENS)))
        except ValueError as exc:
            raise ValueError("OpenAI timeout and token settings must be numeric.") from exc
        return cls(bool(api_key), model, timeout, max_tokens, enabled, api_key,
                   bool(environment_key))

    @classmethod
    def resolve(cls, *, enabled: bool = True, dotenv_path: str | Path = ".env") -> "OpenAIConfig":
        return cls.from_environment(enabled=enabled, dotenv_values=load_optional_dotenv(dotenv_path))
