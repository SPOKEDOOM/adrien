from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.conversation.conversation_context import ConversationContext


class ConversationBackend(ABC):
    """Replaceable local or remote conversation-provider contract."""

    name = "conversation backend"

    def initialize(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    @abstractmethod
    def generate_reply(self, text: str, context: "ConversationContext") -> str:
        raise NotImplementedError
