from dataclasses import dataclass


@dataclass(slots=True)
class VoiceConfig:
    """Central settings for optional local audio backends."""

    enabled: bool = True
    microphone_enabled: bool = True
    tts_enabled: bool = True
    input_device: str | int | None = None
    output_device: str | int | None = None
    sample_rate: int = 16_000
    channels: int = 1
    audio_block_size: int = 1_024
    energy_threshold: float = 0.008
    minimum_usable_rms: float = 0.001
    speech_start_duration: float = 0.15
    silence_stop_duration: float = 1.0
    minimum_speech_duration: float = 0.25
    maximum_recording_duration: float = 10.0
    stt_backend: str = "auto"
    stt_model: str = "tiny.en"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"
    stt_beam_size: int = 5
    stt_download_directory: str | None = None
    language: str = "en"
    tts_backend: str = "auto"
    tts_voice_model: str | None = None
    volume: float = 0.8
    debug_audio: bool = False
    retain_debug_recordings: bool = False

    # Phase 1 compatibility aliases.
    @property
    def microphone(self) -> str:
        return str(self.input_device) if self.input_device is not None else "Default microphone"

    @microphone.setter
    def microphone(self, value: str) -> None:
        self.input_device = value

    @property
    def speaker(self) -> str:
        return str(self.output_device) if self.output_device is not None else "Default speaker"

    @speaker.setter
    def speaker(self, value: str) -> None:
        self.output_device = value

    @property
    def recognizer_backend(self) -> str:
        return self.stt_backend

    @property
    def synthesizer_backend(self) -> str:
        return self.tts_backend
