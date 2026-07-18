from __future__ import annotations

from threading import Lock

from app.voice.stt.base_stt import SpeechToTextBackend
from app.voice.voice_config import VoiceConfig


class FasterWhisperSTT(SpeechToTextBackend):
    """Lazily loads and reuses one faster-whisper model."""

    name = "faster-whisper"

    def __init__(self, config: VoiceConfig, model_factory=None, status_callback=None):
        self.config = config
        self._model_factory = model_factory
        self._model = None
        self._lock = Lock()
        self.status_callback = status_callback

    def _report(self, status: str) -> None:
        if self.status_callback is not None:
            self.status_callback(status)

    @staticmethod
    def available() -> bool:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            return False
        return True

    def _get_model(self):
        with self._lock:
            if self._model is None:
                print("STT model loading", flush=True)
                self._report("model_loading")
                factory = self._model_factory
                if factory is None:
                    from faster_whisper import WhisperModel
                    factory = WhisperModel
                self._model = factory(
                    self.config.stt_model, device=self.config.stt_device,
                    compute_type=self.config.stt_compute_type,
                    download_root=self.config.stt_download_directory,
                )
                print("STT model ready", flush=True)
                self._report("model_ready")
            return self._model

    def transcribe(self, audio_samples, sample_rate: int) -> str:
        if sample_rate != 16_000:
            raise ValueError("faster-whisper input must be sampled at 16000 Hz")
        import numpy as np
        audio = np.asarray(audio_samples, dtype=np.float32)
        segments, _ = self._get_model().transcribe(
            audio, language=self.config.language,
            beam_size=self.config.stt_beam_size,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        print(f"Transcription result: {text or '<empty>'}", flush=True)
        return text
