from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class AIResponse:
    request_id: str
    reply_text: str
    backend_used: str
    model_name: str = ""
    success: bool = True
    error_message: str = ""
    processing_time: float = 0.0
    fallback_used: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.request_id.strip(): raise ValueError("request_id is required")
        if self.success and not self.reply_text.strip(): raise ValueError("successful response requires reply_text")
