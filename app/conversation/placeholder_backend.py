from __future__ import annotations

import re
from datetime import datetime

from app.conversation.conversation_backend import ConversationBackend


class PlaceholderBackend(ConversationBackend):
    name = "placeholder"

    def __init__(self, clock=None) -> None:
        self.clock = clock or datetime.now
        self.initialized = False

    def initialize(self) -> None:
        self.initialized = True

    def shutdown(self) -> None:
        self.initialized = False

    def generate_reply(self, text: str, context, personality=None) -> str:
        phrase = re.sub(r"[^a-z0-9\s]", "", text.casefold()).strip()
        name = str((personality or {}).get("name", "ADRIEN"))
        if phrase in {"hello", "hi", "hey"}:
            return "Hello. Nice to see you."
        if phrase in {"how are you", "how are you doing"}:
            return "I'm functioning normally. Thank you for asking."
        if phrase in {"time", "what time is it", "tell me the time"}:
            return self.clock().strftime("It is %H:%M.")
        if phrase in {"date", "what is the date", "what date is it"}:
            return self.clock().strftime("Today is %B %d, %Y.")
        if phrase in {"who created you", "who made you", "what are you"}:
            return f"I am {name}, currently under development."
        if phrase in {"who are you", "tell me who you are"}:
            return f"I'm {name}, your desktop AI assistant."
        if phrase in {"can you do everything", "can you do anything"}:
            return "Not yet. I'm still under active development."
        return "I understood your request, but I cannot answer that yet."
