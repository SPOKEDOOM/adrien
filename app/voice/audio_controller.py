from __future__ import annotations

from app.voice.voice_config import VoiceConfig


class AudioController:
    """Keeps audio-device preferences independent from platform backends."""

    def __init__(self, config: VoiceConfig):
        self.config = config
        self.muted = False

    @property
    def input_device(self) -> str:
        return self.config.microphone

    @property
    def output_device(self) -> str:
        return self.config.speaker

    def set_input_device(self, device: str) -> None:
        self.config.microphone = device

    def set_output_device(self, device: str) -> None:
        self.config.speaker = device

    def set_volume(self, volume: float) -> None:
        self.config.volume = max(0.0, min(1.0, volume))

    def set_muted(self, muted: bool) -> None:
        self.muted = muted
