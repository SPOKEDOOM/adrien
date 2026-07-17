from dataclasses import dataclass


@dataclass(slots=True)
class VoiceConfig:
    """Backend-neutral voice settings for the foundation layer."""

    enabled: bool = True
    tts_enabled: bool = True
    recognizer_backend: str = "placeholder"
    synthesizer_backend: str = "placeholder"
    microphone: str = "Default microphone"
    speaker: str = "Default speaker"
    volume: float = 0.8
    language: str = "en-US"
