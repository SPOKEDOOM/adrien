from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class AIRequest:
    user_text: str
    request_id: str = field(default_factory=lambda: str(uuid4()))
    conversation_history: tuple = ()
    system_prompt: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    preferred_backend: str = "auto"
    allow_cloud: bool = True
    allow_local: bool = True
    timeout_seconds: float = 30.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.request_id.strip(): raise ValueError("request_id is required")
        if not self.user_text.strip(): raise ValueError("user_text is required")
        if self.timeout_seconds <= 0: raise ValueError("timeout_seconds must be positive")
