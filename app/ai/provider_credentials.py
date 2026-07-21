from __future__ import annotations

import os
from pathlib import Path

from app.ai.groq_config import GroqConfig
from app.ai.openai_config import OpenAIConfig, load_optional_dotenv


class ProviderCredentialService:
    """Single sanitized source for cloud-provider configuration and UI metadata."""

    VARIABLES = {"groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY"}

    def __init__(self, dotenv_path: str | Path = ".env", *, cloud_enabled: bool = True):
        self.dotenv_path = Path(dotenv_path)
        self.cloud_enabled = cloud_enabled
        self._dotenv_values: dict[str, str] = {}
        self.configs = {}
        self.refresh()

    def refresh(self):
        self._dotenv_values = load_optional_dotenv(self.dotenv_path)
        self.configs = {
            "groq": GroqConfig.from_environment(dotenv_values=self._dotenv_values,
                                                enabled=self.cloud_enabled),
            "openai": OpenAIConfig.from_environment(dotenv_values=self._dotenv_values,
                                                      enabled=self.cloud_enabled),
        }
        return self.configs

    def get_provider_key(self, provider: str) -> str:
        config = self.configs.get(provider)
        return getattr(config, "api_key", "") if config else ""

    def get_provider_key_source(self, provider: str) -> str:
        variable = self.VARIABLES.get(provider, "")
        if variable and (os.getenv(variable) or "").strip():
            return "Environment"
        if variable and (self._dotenv_values.get(variable) or "").strip():
            return ".env"
        return "Unavailable"

    def is_provider_configured(self, provider: str) -> bool:
        return bool(self.get_provider_key(provider))

    @staticmethod
    def mask_secret(secret: str) -> str:
        value = (secret or "").strip()
        if not value:
            return "—"
        if len(value) <= 7:
            return "•" * len(value)
        return f"{value[:4]}{'•' * max(4, len(value) - 7)}{value[-3:]}"

    def sanitized(self, provider: str) -> dict[str, object]:
        config = self.configs.get(provider)
        return {
            "configured": self.is_provider_configured(provider),
            "source": self.get_provider_key_source(provider),
            "preview": self.mask_secret(self.get_provider_key(provider)),
            "model": getattr(config, "model", ""),
            "enabled": bool(getattr(config, "enabled", False)),
        }
