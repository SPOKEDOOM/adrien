from __future__ import annotations

import logging
import subprocess
import sys
from threading import Lock, Thread, current_thread

from app.voice.speech_synthesizer import SpeechSynthesizer
from app.voice.voice_config import VoiceConfig

logger = logging.getLogger(__name__)


class WindowsSapiSpeechSynthesizer(SpeechSynthesizer):
    """Dependency-free Windows local TTS fallback using System.Speech."""

    backend_name = "Windows SAPI"

    def __init__(self, config: VoiceConfig) -> None:
        super().__init__()
        self.config = config
        self.is_speaking = False
        self._process = None
        self._lock = Lock()
        self._worker: Thread | None = None
        self._cancelled = False

    @staticmethod
    def available() -> bool:
        return sys.platform == "win32"

    def speak(self, text: str) -> None:
        self.stop()
        self._cancelled = False
        self.is_speaking = True
        self.started.emit()
        self._worker = Thread(target=self._run, args=(text,), name="adrien-sapi", daemon=True)
        self._worker.start()

    def _run(self, text: str) -> None:
        escaped = text.replace("'", "''")
        volume = round(max(0.0, min(1.0, self.config.volume)) * 100)
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$voice.Volume = {volume}; $voice.Speak('{escaped}'); $voice.Dispose()"
        )
        try:
            process = subprocess.Popen(
                ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
                 "-WindowStyle", "Hidden", "-Command", script],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            with self._lock:
                self._process = process
            print("Speech playback started", flush=True)
            _, stderr = process.communicate()
            with self._lock:
                self._process = None
            if process.returncode and not self._cancelled:
                raise RuntimeError(stderr.decode(errors="replace").strip() or "SAPI failed")
            if not self._cancelled:
                self.is_speaking = False
                print("Speech playback completed", flush=True)
                self.finished.emit()
        except Exception as exc:
            self.is_speaking = False
            logger.exception("Windows speech output failed")
            if not self._cancelled:
                self.error.emit(f"Speech output failed: {exc}")

    def stop(self) -> None:
        self._cancelled = True
        self.is_speaking = False
        with self._lock:
            process = self._process
        if process and process.poll() is None:
            process.terminate()

    def shutdown(self) -> None:
        self.stop()
        worker = self._worker
        if worker and worker.is_alive() and worker is not current_thread():
            worker.join(timeout=2.0)
