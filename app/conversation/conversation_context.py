from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class ConversationExchange:
    user_message: str
    adrien_reply: str
    timestamp: datetime


class ConversationContext:
    """Bounded conversation history owned by ConversationManager."""

    def __init__(self, maximum_history: int = 10) -> None:
        self.maximum_history = max(1, int(maximum_history))
        self._exchanges: list[ConversationExchange] = []
        self.interaction_count = 0

    @property
    def exchanges(self) -> tuple[ConversationExchange, ...]:
        return tuple(self._exchanges)

    @property
    def recent_user_messages(self) -> tuple[str, ...]:
        return tuple(exchange.user_message for exchange in self._exchanges)

    @property
    def recent_adrien_replies(self) -> tuple[str, ...]:
        return tuple(exchange.adrien_reply for exchange in self._exchanges)

    def add_exchange(self, user_message: str, adrien_reply: str,
                     timestamp: datetime | None = None) -> ConversationExchange:
        exchange = ConversationExchange(
            user_message=user_message, adrien_reply=adrien_reply,
            timestamp=timestamp or datetime.now(timezone.utc),
        )
        self._exchanges.append(exchange)
        del self._exchanges[:-self.maximum_history]
        self.interaction_count += 1
        return exchange

    def clear(self) -> None:
        self._exchanges.clear()
        self.interaction_count = 0
