from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, Signal


class ApplicationSettings(QObject):
    changed = Signal(str, object)
    PROVIDERS = ("groq", "openai", "local", "placeholder")

    def __init__(self, store: QSettings | None = None, parent=None):
        super().__init__(parent); self.store = store or QSettings()

    def _bool(self, key, default):
        value = self.store.value(key, default)
        return value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes", "on")

    @property
    def default_provider(self): return str(self.store.value("ai/default_provider", "automatic"))
    @property
    def provider_priority(self):
        value = self.store.value("ai/provider_priority", list(self.PROVIDERS))
        if isinstance(value, str): value = [item for item in value.split(",") if item]
        valid = [item for item in value if item in self.PROVIDERS]
        return tuple(valid + [item for item in self.PROVIDERS if item not in valid])
    @property
    def routing_mode(self):
        value = str(self.store.value("ai/routing_mode", "automatic"))
        return value if value in ("groq_first", "openai_first", "automatic") else "automatic"
    @property
    def cloud_processing(self): return self._bool("privacy/cloud_processing", True)
    @property
    def developer_mode(self): return self._bool("developer/mode", True)
    @property
    def diagnostics_enabled(self): return self._bool("developer/diagnostics", True)
    @property
    def debug_logging(self): return self._bool("developer/debug_logging", False)
    @property
    def experimental_features(self): return self._bool("developer/experimental", False)
    @property
    def test_buttons(self): return self._bool("developer/test_buttons", True)
    @property
    def memory_maximum_recent_messages(self): return int(self.store.value("memory/maximum_recent_messages", 30))
    @property
    def memory_summary_threshold(self): return int(self.store.value("memory/summary_threshold", 30))
    @property
    def memory_maximum_summary_words(self): return int(self.store.value("memory/maximum_summary_words", 500))
    @property
    def memory_summaries_enabled(self): return self._bool("memory/conversation_summaries_enabled", True)
    @property
    def long_term_memory_enabled(self): return self._bool("memory/long_term_enabled", True)
    @property
    def memory_suggestions_enabled(self): return self._bool("memory/suggestions_enabled", True)
    @property
    def memory_ask_before_saving(self): return self._bool("memory/ask_before_saving", True)
    @property
    def maximum_long_term_memories(self): return int(self.store.value("memory/maximum_memories", 500))
    @property
    def disabled_memory_suggestion_categories(self):
        value = self.store.value("memory/disabled_suggestion_categories", [])
        if isinstance(value, str): value = [item for item in value.split(",") if item]
        return tuple(value)

    def set_value(self, key, value):
        self.store.setValue(key, value); self.store.sync(); self.changed.emit(key, value)

    def set_default_provider(self, value):
        if value not in ("automatic", *self.PROVIDERS): raise ValueError("Unknown provider")
        self.set_value("ai/default_provider", value)

    def set_provider_priority(self, value):
        ordered = tuple(value)
        if set(ordered) != set(self.PROVIDERS): raise ValueError("Provider priority is invalid")
        self.set_value("ai/provider_priority", list(ordered))

    def set_routing_mode(self, value):
        if value not in ("groq_first", "openai_first", "automatic"):
            raise ValueError("Unknown routing mode")
        self.set_value("ai/routing_mode", value)
