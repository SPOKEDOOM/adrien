from dataclasses import dataclass


DEFAULT_SYSTEM_PROMPT = (
    "You are ADRIEN, a desktop AI assistant currently under development. "
    "Be concise, helpful, calm, and honest about unavailable capabilities."
)


@dataclass(slots=True)
class AIConfig:
    ai_enabled: bool = True
    hybrid_mode: str = "local_first"
    default_backend: str = "auto"
    provider_priority: tuple[str, ...] = ("groq", "openai", "local", "placeholder")
    fallback_enabled: bool = True
    fallback_backend: str = "placeholder"
    local_backend_enabled: bool = True
    cloud_backend_enabled: bool = True
    placeholder_backend_enabled: bool = True
    allow_cloud_by_default: bool = True
    allow_cloud_ai: bool = True
    default_privacy_level: str = "standard"
    request_timeout_seconds: float = 30.0
    backend_health_check_enabled: bool = True
    internet_available: bool = True
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
