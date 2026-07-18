from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Signal

from app.wake.wake_backend import WakeBackend
from app.wake.wake_config import WakeConfig


@dataclass(frozen=True, slots=True)
class WakeResult:
    phrase: str
    confidence: float
    timestamp: datetime
    backend: str


class WakeDetector(QObject):
    candidate = Signal(object)
    error = Signal(str)
    status_changed = Signal(str)

    def __init__(self, backend: WakeBackend, config: WakeConfig) -> None:
        super().__init__()
        self.backend = backend
        self.config = config
        backend.candidate.connect(self._on_candidate)
        backend.error.connect(self.error)
        backend.status_changed.connect(self.status_changed)

    @staticmethod
    def normalize_phrase(phrase: str) -> str:
        return " ".join(phrase.casefold().strip().split())

    def _on_candidate(self, phrase: str, confidence: float) -> None:
        confidence = max(0.0, min(1.0, float(confidence)))
        self.candidate.emit(WakeResult(phrase.strip(), confidence,
                                      datetime.now(timezone.utc), self.backend.name))

    def phrase_matches(self, phrase: str) -> bool:
        normalized = self.normalize_phrase(phrase)
        configured = self.normalize_phrase(self.config.wake_phrase)
        return normalized in {configured, "adrian", f"hey {configured}"}
