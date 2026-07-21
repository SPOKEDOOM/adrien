from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock

from app.conversation.conversation_context import ConversationExchange


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    text: str
    created_timestamp: datetime
    last_updated_timestamp: datetime
    message_count_represented: int


class ConversationMemory:
    """Session-only rolling conversation memory with recent detail and a summary."""

    def __init__(self, maximum_recent_messages=30, summary_threshold=30,
                 maximum_summary_words=500, summaries_enabled=True):
        self.maximum_recent_messages = max(2, int(maximum_recent_messages))
        self.summary_threshold = max(2, int(summary_threshold))
        self.maximum_summary_words = max(20, int(maximum_summary_words))
        self.summaries_enabled = bool(summaries_enabled)
        self._exchanges: list[ConversationExchange] = []
        self.summary: ConversationSummary | None = None
        self.interaction_count = 0; self.summarizing = False; self.status = "Ready"
        self._lock = Lock()

    @property
    def exchanges(self):
        with self._lock: return tuple(self._exchanges)
    @property
    def recent_user_messages(self): return tuple(item.user_message for item in self.exchanges)
    @property
    def recent_adrien_replies(self): return tuple(item.adrien_reply for item in self.exchanges)
    @property
    def recent_message_count(self): return len(self.exchanges) * 2
    @property
    def estimated_tokens(self):
        text = " ".join(f"{e.user_message} {e.adrien_reply}" for e in self.exchanges)
        if self.summary: text = f"{self.summary.text} {text}"
        return max(0, round(len(text.split()) * 1.35))

    def add_exchange(self, user_message, adrien_reply, timestamp=None):
        exchange = ConversationExchange(user_message, adrien_reply,
                                        timestamp or datetime.now(timezone.utc))
        with self._lock: self._exchanges.append(exchange); self.interaction_count += 1
        return exchange

    def summary_candidates(self, *, force=False):
        with self._lock:
            if self.summarizing or not self.summaries_enabled: return ()
            if not force and len(self._exchanges) * 2 <= self.summary_threshold: return ()
            keep = max(1, self.maximum_recent_messages // 2)
            count = len(self._exchanges) - keep
            if force and count <= 0: count = len(self._exchanges)
            if count <= 0: return ()
            self.summarizing = True; self.status = "Summarizing..."
            return tuple(self._exchanges[:count])

    def apply_summary(self, text, represented):
        normalized = " ".join(str(text).split())
        normalized = " ".join(normalized.split()[:self.maximum_summary_words])
        now = datetime.now(timezone.utc)
        with self._lock:
            prior = self.summary.message_count_represented if self.summary else 0
            created = self.summary.created_timestamp if self.summary else now
            self.summary = ConversationSummary(normalized, created, now, prior + len(represented) * 2)
            remove = 0
            for expected, actual in zip(represented, self._exchanges):
                if expected != actual: break
                remove += 1
            del self._exchanges[:remove]
            self.summarizing = False; self.status = "Summary updated."

    def summary_failed(self):
        with self._lock: self.summarizing = False; self.status = "Summary unavailable."

    def deterministic_summary(self, represented):
        parts = [self.summary.text] if self.summary else []
        for exchange in represented:
            parts.append(f"User requested: {exchange.user_message}. ADRIEN replied: {exchange.adrien_reply}.")
        return " ".join(" ".join(parts).split())

    def clear(self):
        with self._lock:
            self._exchanges.clear(); self.summary = None; self.interaction_count = 0
            self.summarizing = False; self.status = "Ready"
