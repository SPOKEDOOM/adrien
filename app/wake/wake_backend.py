from __future__ import annotations

from abc import abstractmethod

from PySide6.QtCore import QObject, Signal


class WakeBackend(QObject):
    candidate = Signal(str, float)
    error = Signal(str)
    status_changed = Signal(str)
    name = "abstract"

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    def shutdown(self) -> None:
        self.stop()


class DevelopmentWakeBackend(WakeBackend):
    """Deterministic fallback; owns no audio stream and supports confidence injection."""

    name = "development simulation"

    def __init__(self) -> None:
        super().__init__()
        self.active = False

    def start(self) -> None:
        if self.active:
            return
        self.active = True
        self.status_changed.emit("monitoring")

    def stop(self) -> None:
        if not self.active:
            return
        self.active = False
        self.status_changed.emit("stopped")

    def inject(self, phrase: str, confidence: float) -> None:
        if self.active:
            self.candidate.emit(phrase, confidence)
