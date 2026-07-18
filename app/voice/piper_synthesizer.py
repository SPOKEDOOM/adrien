from __future__ import annotations

import logging
from array import array
from io import BytesIO
from threading import Event, Lock, Thread, current_thread
import wave

from app.voice.speech_synthesizer import SpeechSynthesizer
from app.voice.voice_config import VoiceConfig

logger = logging.getLogger(__name__)


class PiperSpeechSynthesizer(SpeechSynthesizer):
    """Piper synthesis and sounddevice playback on one background worker."""

    backend_name = "piper"

    def __init__(self, config: VoiceConfig, voice_factory=None, sounddevice_module=None) -> None:
        super().__init__()
        self.config = config
        self._voice_factory = voice_factory
        self._sounddevice = sounddevice_module
        self._voice = None
        self._voice_lock = Lock()
        self._cancelled = Event()
        self._worker: Thread | None = None
        self.is_speaking = False

    @staticmethod
    def available(config: VoiceConfig) -> bool:
        if not config.tts_voice_model:
            return False
        try:
            import numpy  # noqa: F401
            import piper  # noqa: F401
            import sounddevice  # noqa: F401
        except ImportError:
            return False
        return True

    def _get_voice(self):
        with self._voice_lock:
            if self._voice is None:
                factory = self._voice_factory
                if factory is None:
                    from piper import PiperVoice
                    factory = PiperVoice.load
                self._voice = factory(self.config.tts_voice_model)
            return self._voice

    def speak(self, text: str) -> None:
        self.stop()
        self._cancelled.clear()
        self.is_speaking = True
        self.started.emit()
        self._worker = Thread(target=self._run, args=(text,), name="adrien-tts", daemon=True)
        self._worker.start()

    def _run(self, text: str) -> None:
        try:
            buffer = BytesIO()
            with wave.open(buffer, "wb") as wav_file:
                self._get_voice().synthesize_wav(text, wav_file)
            buffer.seek(0)
            with wave.open(buffer, "rb") as wav_file:
                rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                audio = array("h")
                audio.frombytes(wav_file.readframes(wav_file.getnframes()))
                if channels > 1:
                    audio = [audio[index:index + channels]
                             for index in range(0, len(audio), channels)]
            if self._cancelled.is_set():
                return
            module = self._sounddevice
            if module is None:
                import sounddevice as module
            print("Speech playback started", flush=True)
            module.play(audio, rate, device=self.config.output_device)
            module.wait()
            if not self._cancelled.is_set():
                self.is_speaking = False
                print("Speech playback completed", flush=True)
                self.finished.emit()
        except Exception as exc:
            self.is_speaking = False
            logger.exception("Speech synthesis/playback failed")
            if not self._cancelled.is_set():
                self.error.emit(f"Speech output failed: {exc}")

    def stop(self) -> None:
        self._cancelled.set()
        self.is_speaking = False
        module = self._sounddevice
        try:
            if module is not None:
                module.stop()
            else:
                import sounddevice
                sounddevice.stop()
        except (ImportError, Exception):
            pass

    def shutdown(self) -> None:
        self.stop()
        worker = self._worker
        if worker and worker.is_alive() and worker is not current_thread():
            worker.join(timeout=2.0)
