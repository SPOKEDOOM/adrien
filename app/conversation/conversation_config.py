from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConversationConfig:
    conversation_backend: str = "placeholder"
    maximum_history: int = 10
    processing_timeout_seconds: float = 10.0
    maximum_recent_messages: int = 30
    summary_threshold: int = 30
    maximum_summary_words: int = 500
    conversation_summaries_enabled: bool = True
