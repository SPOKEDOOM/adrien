from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, Signal

from app.core.presence_state import PresenceState
from app.core.presence_state_manager import PresenceStateManager
from app.voice.audio_controller import AudioController
from app.voice.speech_recognizer import PlaceholderSpeechRecognizer, SpeechRecognizer
from app.voice.speech_synthesizer import PlaceholderSpeechSynthesizer, SpeechSynthesizer
from app.voice.microphone_recognizer import MicrophoneSpeechRecognizer
from app.voice.piper_synthesizer import PiperSpeechSynthesizer
from app.voice.stt.faster_whisper_stt import FasterWhisperSTT
from app.voice.windows_sapi_synthesizer import WindowsSapiSpeechSynthesizer
from app.voice.voice_config import VoiceConfig


class VoiceManager(QObject):
    """Coordinates voice stages and state changes without UI or renderer knowledge."""

    listening_changed = Signal(bool)
    recognized_text = Signal(str)
    reply_generated = Signal(str)
    speaking_changed = Signal(bool)
    error = Signal(str)
    status_changed = Signal(str)
    level_changed = Signal(float)
    rms_changed = Signal(float)
    speech_changed = Signal(bool)
    duration_changed = Signal(float)

    def __init__(
        self, state_manager: PresenceStateManager, config: VoiceConfig | None = None,
        recognizer: SpeechRecognizer | None = None, synthesizer: SpeechSynthesizer | None = None,
    ) -> None:
        super().__init__()
        self.state_manager = state_manager
        self.config = config or VoiceConfig()
        self.audio_controller = AudioController(self.config)
        self.recognizer = recognizer or self._create_recognizer()
        self.synthesizer = synthesizer or self._create_synthesizer()
        self.recognizer.recognized.connect(self._on_recognized)
        self.recognizer.error.connect(self._on_error)
        self.recognizer.status_changed.connect(self._on_recognizer_status)
        self.recognizer.level_changed.connect(self.level_changed)
        self.recognizer.rms_changed.connect(self.rms_changed)
        self.recognizer.speech_changed.connect(self.speech_changed)
        self.recognizer.duration_changed.connect(self.duration_changed)
        self.synthesizer.started.connect(self._on_speaking_started)
        self.synthesizer.finished.connect(self._on_finished)
        self.synthesizer.error.connect(self._on_error)

    def _create_recognizer(self) -> SpeechRecognizer:
        use_real = self.config.stt_backend in ("auto", "faster-whisper")
        if use_real and MicrophoneSpeechRecognizer.available():
            return MicrophoneSpeechRecognizer(self.config, FasterWhisperSTT(self.config))
        return PlaceholderSpeechRecognizer()

    def _create_synthesizer(self) -> SpeechSynthesizer:
        use_real = self.config.tts_backend in ("auto", "piper")
        if use_real and PiperSpeechSynthesizer.available(self.config):
            return PiperSpeechSynthesizer(self.config)
        if self.config.tts_backend in ("auto", "sapi") and WindowsSapiSpeechSynthesizer.available():
            return WindowsSapiSpeechSynthesizer(self.config)
        return PlaceholderSpeechSynthesizer()

    @property
    def microphone_backend(self) -> str:
        return getattr(self.recognizer, "backend_name", "typed placeholder")

    @property
    def stt_backend(self) -> str:
        backend = getattr(self.recognizer, "stt_backend", None)
        return getattr(backend, "name", "placeholder")

    @property
    def tts_backend(self) -> str:
        return getattr(self.synthesizer, "backend_name", "placeholder")

    def start_listening(self) -> bool:
        if not self.config.enabled or self.state_manager.current_state is not PresenceState.READY:
            return False
        print("Voice listening requested", flush=True)
        if not self.state_manager.transition_to(PresenceState.LISTENING):
            return False
        self.listening_changed.emit(True)
        self.status_changed.emit("listening")
        self.recognizer.start()
        return self.state_manager.current_state is PresenceState.LISTENING

    def stop_listening(self) -> None:
        """Finalize captured audio and transcribe it; unlike cancel, retains samples."""
        if self.state_manager.current_state is PresenceState.LISTENING:
            self.recognizer.stop()

    def submit_debug_text(self, text: str) -> bool:
        """Feed the local placeholder recognizer from the development panel."""
        normalized = text.strip()
        if not normalized:
            return False
        if self.state_manager.current_state is PresenceState.READY:
            if not self.state_manager.transition_to(PresenceState.LISTENING):
                return False
            self.listening_changed.emit(True)
        if self.state_manager.current_state is not PresenceState.LISTENING:
            return False
        print(f"Voice input submitted: {normalized}", flush=True)
        submit = getattr(self.recognizer, "submit_text", None)
        if callable(submit):
            if not getattr(self.recognizer, "is_listening", False):
                self.recognizer.start()
            submit(normalized)
        else:
            # Typed input remains independent of optional microphone dependencies.
            self.recognizer.cancel()
            print(f"Voice recognized: {normalized}", flush=True)
            self._on_recognized(normalized)
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
        print(f"VoiceManager received recognized: {text}", flush=True)
        self.listening_changed.emit(False)
        self.recognized_text.emit(text)
        if (self.state_manager.current_state is PresenceState.LISTENING and
                not self.state_manager.transition_to(PresenceState.THINKING)):
            self._return_ready()
            return
        if self.state_manager.current_state is not PresenceState.THINKING:
            self._return_ready()
            return
        reply = self.placeholder_reply(text)
        print(f"Voice reply generated: {reply}", flush=True)
        self.reply_generated.emit(reply)
        if not self.config.tts_enabled or self.audio_controller.muted:
            self._return_ready()
            return
        if self.state_manager.transition_to(PresenceState.RESPONDING):
            self.speaking_changed.emit(True)
            self.synthesizer.speak(reply)

    def _on_recognizer_status(self, status: str) -> None:
        self.status_changed.emit(status)
        if status == "transcribing" and self.state_manager.current_state is PresenceState.LISTENING:
            self.listening_changed.emit(False)
            self.state_manager.transition_to(PresenceState.THINKING)

    def _on_finished(self) -> None:
        print("TTS completed", flush=True)
        self.speaking_changed.emit(False)
        self._return_ready()

    def _on_speaking_started(self) -> None:
        print("TTS started", flush=True)
        self.status_changed.emit("playing")

    def _on_error(self, message: str) -> None:
        self.error.emit(message)
        self.cancel()

    def _return_ready(self) -> None:
        if self.state_manager.current_state is not PresenceState.READY:
            if self.state_manager.transition_to(PresenceState.READY):
                print("Voice pipeline returned to READY", flush=True)

    def shutdown(self) -> None:
        self.cancel()
        self.recognizer.shutdown()
        self.synthesizer.shutdown()
