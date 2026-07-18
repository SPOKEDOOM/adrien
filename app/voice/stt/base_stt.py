from __future__ import annotations

from abc import ABC, abstractmethod


class SpeechToTextBackend(ABC):
    name = "abstract"

    @abstractmethod
    def transcribe(self, audio_samples, sample_rate: int) -> str:
        """Return normalized text for mono float PCM samples."""

