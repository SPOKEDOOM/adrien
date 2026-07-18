from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal


class SpeechSynthesizer(QObject):
    """Replaceable text-to-speech contract."""

    started = Signal()
    finished = Signal()
    error = Signal(str)

    def speak(self, text: str) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def shutdown(self) -> None:
        self.stop()


class PlaceholderSpeechSynthesizer(SpeechSynthesizer):
    """Local asynchronous stand-in that preserves the real TTS lifecycle."""

    def __init__(self) -> None:
        super().__init__()
        self.is_speaking = False
        self.last_text = ""

    def speak(self, text: str) -> None:
        self.stop()
        self.last_text = text
        self.is_speaking = True
        self.started.emit()
        QTimer.singleShot(1, self._finish)

    def stop(self) -> None:
        self.is_speaking = False

    def _finish(self) -> None:
        if self.is_speaking:
            self.is_speaking = False
            self.finished.emit()
