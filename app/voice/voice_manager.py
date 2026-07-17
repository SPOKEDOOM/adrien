from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, Signal

from app.core.presence_state import PresenceState
from app.core.presence_state_manager import PresenceStateManager
from app.voice.audio_controller import AudioController
from app.voice.speech_recognizer import PlaceholderSpeechRecognizer, SpeechRecognizer
from app.voice.speech_synthesizer import PlaceholderSpeechSynthesizer, SpeechSynthesizer
from app.voice.voice_config import VoiceConfig


class VoiceManager(QObject):
    """Coordinates voice stages and state changes without UI or renderer knowledge."""

    listening_changed = Signal(bool)
    recognized_text = Signal(str)
    reply_generated = Signal(str)
    speaking_changed = Signal(bool)
    error = Signal(str)

    def __init__(
        self, state_manager: PresenceStateManager, config: VoiceConfig | None = None,
        recognizer: SpeechRecognizer | None = None, synthesizer: SpeechSynthesizer | None = None,
    ) -> None:
        super().__init__()
        self.state_manager = state_manager
        self.config = config or VoiceConfig()
        self.audio_controller = AudioController(self.config)
        self.recognizer = recognizer or PlaceholderSpeechRecognizer()
        self.synthesizer = synthesizer or PlaceholderSpeechSynthesizer()
        self.recognizer.recognized.connect(self._on_recognized)
        self.recognizer.error.connect(self._on_error)
        self.synthesizer.finished.connect(self._on_finished)
        self.synthesizer.error.connect(self._on_error)

    def start_listening(self) -> bool:
        if not self.config.enabled or self.state_manager.current_state is not PresenceState.READY:
            return False
        if not self.state_manager.transition_to(PresenceState.LISTENING):
            return False
        self.recognizer.start()
        self.listening_changed.emit(True)
        return True

    def submit_debug_text(self, text: str) -> bool:
        """Feed the local placeholder recognizer from the development panel."""
        normalized = text.strip()
        if not normalized:
            return False
        if self.state_manager.current_state is PresenceState.READY:
            if not self.start_listening():
                return False
        if self.state_manager.current_state is not PresenceState.LISTENING:
            return False
        submit = getattr(self.recognizer, "submit_text", None)
        if not callable(submit):
            self._on_error("The selected recognizer does not support debug text input.")
            return False
        print(f"Voice input submitted: {normalized}", flush=True)
        submit(normalized)
        return True

    def cancel(self) -> None:
        self.recognizer.cancel()
        self.synthesizer.stop()
        self.listening_changed.emit(False)
        self.speaking_changed.emit(False)
        self._return_ready()

    @staticmethod
    def placeholder_reply(text: str, now: datetime | None = None) -> str:
        phrase = text.strip().lower()
        current = now or datetime.now()
        if phrase == "hello":
            return "Hello. Nice to see you."
        if phrase == "time":
            return current.strftime("It is %H:%M.")
        if phrase == "date":
            return current.strftime("Today is %B %d, %Y.")
        return "I'm ready for the next stage of my intelligence."

    def _on_recognized(self, text: str) -> None:
        self.listening_changed.emit(False)
        self.recognized_text.emit(text)
        if not self.state_manager.transition_to(PresenceState.THINKING):
            self._return_ready()
            return
        reply = self.placeholder_reply(text)
        print(f"Voice reply: {reply}", flush=True)
        self.reply_generated.emit(reply)
        if not self.config.tts_enabled or self.audio_controller.muted:
            self._return_ready()
            return
        if self.state_manager.transition_to(PresenceState.RESPONDING):
            self.speaking_changed.emit(True)
            self.synthesizer.speak(reply)

    def _on_finished(self) -> None:
        self.speaking_changed.emit(False)
        self._return_ready()

    def _on_error(self, message: str) -> None:
        self.error.emit(message)
        self.cancel()

    def _return_ready(self) -> None:
        if self.state_manager.current_state is not PresenceState.READY:
            self.state_manager.transition_to(PresenceState.READY)
