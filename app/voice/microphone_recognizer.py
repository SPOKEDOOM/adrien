from __future__ import annotations

import logging
from math import sqrt
from threading import Lock, Thread, current_thread

from PySide6.QtCore import QTimer

from app.voice.speech_recognizer import SpeechRecognizer
from app.voice.voice_config import VoiceConfig

logger = logging.getLogger(__name__)


class MicrophoneSpeechRecognizer(SpeechRecognizer):
    """PortAudio capture with energy endpointing and background transcription."""

    backend_name = "sounddevice"

    def __init__(self, config: VoiceConfig, stt_backend, sounddevice_module=None) -> None:
        super().__init__()
        self.config = config
        self.stt_backend = stt_backend
        self._sounddevice = sounddevice_module
        self._stream = None
        self._blocks = []
        self._lock = Lock()
        self._worker: Thread | None = None
        self._generation = 0
        self.is_listening = False
        self.speech_detected = False
        self._speech_frames = 0
        self._silence_frames = 0
        self._total_frames = 0
        self._finalizing = False
        self._manual_finalize = False
        self._callback_count = 0
        self._last_level_log_frame = 0
        self._last_duration_emit_frame = 0
        self._silence_logged = False
        if hasattr(self.stt_backend, "status_callback"):
            self.stt_backend.status_callback = self.status_changed.emit

    @staticmethod
    def available() -> bool:
        try:
            import sounddevice  # noqa: F401
            from app.voice.stt.faster_whisper_stt import FasterWhisperSTT
        except ImportError:
            return False
        return FasterWhisperSTT.available()

    def _module(self):
        if self._sounddevice is not None:
            return self._sounddevice
        import sounddevice
        return sounddevice

    def start(self) -> None:
        if self.is_listening:
            return
        if not self.config.microphone_enabled:
            self.error.emit("Microphone input is disabled.")
            return
        self._reset_capture()
        self.is_listening = True
        self.status_changed.emit("listening")
        try:
            self._stream = self._module().InputStream(
                device=self.config.input_device, samplerate=self.config.sample_rate,
                channels=self.config.channels, blocksize=self.config.audio_block_size,
                dtype="float32", callback=self._audio_callback,
                finished_callback=self._stream_finished,
            )
            self._stream.start()
        except Exception as exc:
            self.is_listening = False
            self._stream = None
            logger.exception("Unable to start microphone")
            self.error.emit(f"Unable to start microphone: {exc}")
            return
        device = self.config.input_device if self.config.input_device is not None else "system default"
        print(f"Microphone stream opened: {device}", flush=True)
        QTimer.singleShot(2000, lambda generation=self._generation:
                          self._verify_audio_received(generation))

    def _verify_audio_received(self, generation: int) -> None:
        if generation == self._generation and self.is_listening and self._callback_count == 0:
            self.error.emit("Microphone opened, but no audio data received.")

    def _reset_capture(self) -> None:
        with self._lock:
            self._blocks.clear()
        self.speech_detected = False
        self._speech_frames = self._silence_frames = self._total_frames = 0
        self._finalizing = False
        self._manual_finalize = False
        self._callback_count = 0
        self._last_level_log_frame = self._last_duration_emit_frame = 0
        self._silence_logged = False
        self._generation += 1

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if status:
            logger.warning("Microphone stream status: %s", status)
        try:
            if self._callback_count == 0:
                print("Audio callback active", flush=True)
            self.process_audio_block(indata)
        except Exception:
            logger.exception("Audio callback failed")
            raise self._module().CallbackAbort
        if self._finalizing:
            raise self._module().CallbackStop

    def process_audio_block(self, samples) -> bool:
        """Process one block; public for deterministic hardware-free tests."""
        if not self.is_listening or self._finalizing:
            return False
        source = samples.reshape(-1) if hasattr(samples, "reshape") else samples
        mono = [float(value) for value in source]
        frames = len(mono)
        if not frames:
            return False
        level = sqrt(sum(value * value for value in mono) / frames)
        self._callback_count += 1
        self.rms_changed.emit(level)
        self.level_changed.emit(min(1.0, level / max(self.config.energy_threshold, 1e-6)))
        self._total_frames += frames
        if self._total_frames - self._last_level_log_frame >= self.config.sample_rate:
            print(f"Input level: {level:.5f}", flush=True)
            self._last_level_log_frame = self._total_frames
        if self._total_frames - self._last_duration_emit_frame >= self.config.sample_rate // 4:
            self.duration_changed.emit(self._total_frames / self.config.sample_rate)
            self._last_duration_emit_frame = self._total_frames
        voiced = level >= self.config.energy_threshold
        if voiced:
            self._speech_frames += frames
            self._silence_frames = 0
            if not self.speech_detected and self._speech_frames >= int(
                    self.config.speech_start_duration * self.config.sample_rate):
                self.speech_detected = True
                print("Speech detected", flush=True)
                self.speech_changed.emit(True)
        elif self.speech_detected:
            self._silence_frames += frames
            if not self._silence_logged:
                print("Silence detected", flush=True)
                self._silence_logged = True
        else:
            self._speech_frames = 0
        if voiced:
            self._silence_logged = False
        with self._lock:
            self._blocks.append(mono)
        ended = self.speech_detected and self._silence_frames >= int(
            self.config.silence_stop_duration * self.config.sample_rate)
        timed_out = self._total_frames >= int(
            self.config.maximum_recording_duration * self.config.sample_rate)
        if ended or timed_out:
            self._finalizing = True
            print("Speech ended" if ended else "Maximum recording duration reached", flush=True)
            return True
        return False

    def _stream_finished(self) -> None:
        if self.is_listening and self._finalizing:
            self._begin_transcription()

    def stop(self) -> None:
        if not self.is_listening:
            return
        self._finalizing = True
        self._manual_finalize = True
        stream = self._stream
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                logger.exception("Unable to close microphone stream")
            self._stream = None
        self._begin_transcription()

    def _begin_transcription(self) -> None:
        if not self.is_listening:
            return
        self.is_listening = False
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.close()
            except Exception:
                logger.exception("Unable to release microphone stream")
        with self._lock:
            blocks = tuple(self._blocks)
            self._blocks.clear()
        generation = self._generation
        print("Recording finalized", flush=True)
        print(f"Recorded samples: {sum(len(block) for block in blocks)}", flush=True)
        self.status_changed.emit("transcribing")
        self._worker = Thread(target=self._transcribe, args=(blocks, generation),
                              name="adrien-stt", daemon=True)
        self._worker.start()

    def _transcribe(self, blocks, generation: int) -> None:
        try:
            import numpy as np
            audio = np.asarray([sample for block in blocks for sample in block], dtype=np.float32)
            duration = len(audio) / self.config.sample_rate
            print(f"Recorded duration: {duration:.2f}s", flush=True)
            if not len(audio):
                raise ValueError("Recording was empty. Check microphone selection.")
            if not np.isfinite(audio).all():
                raise ValueError("Recording contained invalid audio samples.")
            rms = float(np.sqrt(np.mean(audio * audio)))
            peak = float(np.max(np.abs(audio)))
            usable = duration >= self.config.minimum_speech_duration and (
                rms >= self.config.minimum_usable_rms and peak >= self.config.minimum_usable_rms
            )
            automatic_valid = self.speech_detected and (
                self._speech_frames / self.config.sample_rate >= self.config.minimum_speech_duration
            )
            if not usable or (not self._manual_finalize and not automatic_valid):
                raise ValueError(
                    "No usable speech detected. Check microphone selection or lower the threshold."
                )
            print("Transcription worker started", flush=True)
            text = self.stt_backend.transcribe(audio, self.config.sample_rate).strip()
            if not text:
                raise ValueError("Speech-to-text returned no recognized text.")
            if generation == self._generation:
                self.status_changed.emit("complete")
                print("Recognizer emitted recognized", flush=True)
                self.recognized.emit(text)
        except Exception as exc:
            logger.exception("Transcription failed")
            if generation == self._generation:
                self.status_changed.emit("error")
                self.error.emit(str(exc))

    def cancel(self) -> None:
        self._generation += 1
        self.is_listening = False
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.abort()
                stream.close()
            except Exception:
                logger.exception("Unable to cancel microphone stream")
        with self._lock:
            self._blocks.clear()
        self.status_changed.emit("cancelled")
        self.level_changed.emit(0.0)
        self.rms_changed.emit(0.0)
        self.speech_changed.emit(False)
        self.duration_changed.emit(0.0)

    def shutdown(self) -> None:
        self.cancel()
        worker = self._worker
        if worker and worker.is_alive() and worker is not current_thread():
            worker.join(timeout=2.0)
