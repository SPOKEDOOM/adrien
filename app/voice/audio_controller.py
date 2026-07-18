from __future__ import annotations

from dataclasses import dataclass

from app.voice.voice_config import VoiceConfig


@dataclass(frozen=True, slots=True)
class AudioDevice:
    index: int
    name: str
    input_channels: int
    output_channels: int
    default_sample_rate: float


class AudioController:
    """Enumerates and validates PortAudio devices without requiring sounddevice."""

    def __init__(self, config: VoiceConfig, sounddevice_module=None):
        self.config = config
        self.muted = False
        self._sounddevice = sounddevice_module

    def _module(self):
        if self._sounddevice is not None:
            return self._sounddevice
        try:
            import sounddevice
        except ImportError:
            return None
        return sounddevice

    def devices(self) -> list[AudioDevice]:
        module = self._module()
        if module is None:
            return []
        try:
            return [AudioDevice(i, str(d["name"]), int(d["max_input_channels"]),
                                int(d["max_output_channels"]), float(d["default_samplerate"]))
                    for i, d in enumerate(module.query_devices())]
        except Exception:
            return []

    def input_devices(self) -> list[AudioDevice]:
        return [device for device in self.devices() if device.input_channels > 0]

    def output_devices(self) -> list[AudioDevice]:
        return [device for device in self.devices() if device.output_channels > 0]

    @property
    def input_device(self) -> str:
        return self._display_name(self.config.input_device, True)

    @property
    def output_device(self) -> str:
        return self._display_name(self.config.output_device, False)

    def _display_name(self, selection, is_input: bool) -> str:
        if selection is None:
            return "System default"
        for device in (self.input_devices() if is_input else self.output_devices()):
            if selection in (device.index, device.name):
                return device.name
        return str(selection)

    def set_input_device(self, device: str | int | None) -> None:
        self.config.input_device = device

    def set_output_device(self, device: str | int | None) -> None:
        self.config.output_device = device

    def set_volume(self, volume: float) -> None:
        self.config.volume = max(0.0, min(1.0, volume))

    def set_muted(self, muted: bool) -> None:
        self.muted = muted

    @property
    def available(self) -> bool:
        return self._module() is not None
