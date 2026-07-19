from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConversationConfig:
    conversation_backend: str = "placeholder"
    maximum_history: int = 10
    processing_timeout_seconds: float = 10.0
