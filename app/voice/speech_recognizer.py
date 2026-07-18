from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class SpeechRecognizer(QObject):
    """Replaceable speech-to-text contract; backends emit only text or errors."""

    recognized = Signal(str)
    error = Signal(str)
    level_changed = Signal(float)
    rms_changed = Signal(float)
    speech_changed = Signal(bool)
    duration_changed = Signal(float)
    status_changed = Signal(str)

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def cancel(self) -> None:
        raise NotImplementedError

    def shutdown(self) -> None:
        self.cancel()


class PlaceholderSpeechRecognizer(SpeechRecognizer):
    """Local development recognizer. `submit_text` stands in for captured speech."""

    def __init__(self) -> None:
        super().__init__()
        self.is_listening = False

    def start(self) -> None:
        self.is_listening = True

    def stop(self) -> None:
        self.is_listening = False

    def cancel(self) -> None:
        self.stop()

    def submit_text(self, text: str) -> None:
        if not self.is_listening:
            return
        normalized = text.strip()
        if not normalized:
            self.error.emit("No speech was recognized.")
            return
        self.stop()
        print(f"Voice recognized: {normalized}", flush=True)
        self.recognized.emit(normalized)
