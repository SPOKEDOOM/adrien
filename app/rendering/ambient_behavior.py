from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum, auto

from app.core.presence_state import PresenceState


class AmbientMode(Enum):
    CALM = auto()
    BREATHING = auto()
    ENERGY_DRIFT = auto()
    RING_RESONANCE = auto()
    DEEP_IDLE = auto()


@dataclass(frozen=True, slots=True)
class AmbientConfig:
    enabled: bool = True
    debug_seed: int = 42
    transition_duration: float = 2.4
    glow_limit: float = 0.045
    breathing_limit: float = 0.018
    ring_drift_limit: float = 0.035
    ring_wobble_degrees: float = 0.42
    particle_energy_limit: float = 0.045
    particle_spread_limit: float = 0.025
    highlight_limit: float = 0.04
    mode_durations: tuple[tuple[float, float], ...] = (
        (8.0, 16.0), (6.0, 12.0), (7.0, 14.0), (5.0, 10.0), (10.0, 20.0),
    )


STATE_AMBIENT_STRENGTH: dict[PresenceState, float] = {
    PresenceState.BOOTING: 0.0,
    PresenceState.MATERIALIZING: 0.0,
    PresenceState.READY: 1.0,
    PresenceState.LISTENING: 0.35,
    PresenceState.THINKING: 0.22,
    PresenceState.RESPONDING: 0.10,
    PresenceState.SLEEP: 0.42,
}


@dataclass(slots=True)
class AmbientValues:
    glow_variation: float = 0.0
    core_breathing: float = 0.0
    ring_drift: float = 0.0
    ring_wobble: float = 0.0
    particle_energy: float = 0.0
    particle_spread: float = 0.0
    highlight_variation: float = 0.0
    pulse_offset: float = 0.0


class AmbientBehaviorController:
    """Produces bounded, slowly changing visual modulation without drawing."""

    def __init__(self, config: AmbientConfig | None = None, seed: int | None = None):
        self.config = config or AmbientConfig()
        self.seed = self.config.debug_seed if seed is None else seed
        self.rng = random.Random(self.seed)
        self.enabled = self.config.enabled
        self.mode = AmbientMode.CALM
        self.previous_mode = self.mode
        self.mode_elapsed = 0.0
        self.mode_duration = self._select_duration(self.mode)
        self.transition_progress = 1.0
        self.elapsed = 0.0
        self.strength = 0.0
        self.values = AmbientValues()
        self._ring_phases = tuple(self.rng.uniform(0.0, math.tau) for _ in range(5))

    def update(self, delta_seconds: float, state: PresenceState) -> AmbientValues:
        delta = min(max(delta_seconds, 0.0), 0.1)
        self.elapsed += delta
        self.mode_elapsed += delta
        target_strength = STATE_AMBIENT_STRENGTH[state] if self.enabled else 0.0
        if state in (PresenceState.BOOTING, PresenceState.MATERIALIZING):
            self.strength = 0.0
        else:
            self.strength += (target_strength - self.strength) * min(1.0, delta * 1.5)
        if self.mode_elapsed >= self.mode_duration:
            self._choose_next_mode()
        self.transition_progress = min(1.0, self.transition_progress + delta / self.config.transition_duration)
        blend = self.transition_progress * self.transition_progress * (3.0 - 2.0 * self.transition_progress)
        self._calculate_values(self.strength, blend)
        return self.values

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def cycle_mode(self) -> AmbientMode:
        modes = tuple(AmbientMode)
        self._set_mode(modes[(modes.index(self.mode) + 1) % len(modes)])
        return self.mode

    def reseed(self, seed: int | None = None) -> int:
        self.seed = self.rng.randrange(1, 2**31) if seed is None else seed
        self.rng.seed(self.seed)
        self._ring_phases = tuple(self.rng.uniform(0.0, math.tau) for _ in range(5))
        self._set_mode(AmbientMode.CALM)
        return self.seed

    def ring_phase(self, index: int) -> float:
        return self._ring_phases[index % len(self._ring_phases)]

    def _choose_next_mode(self) -> None:
        choices = [mode for mode in AmbientMode if mode is not self.mode]
        self._set_mode(self.rng.choices(choices, weights=(4, 3, 3, 2), k=1)[0])

    def _set_mode(self, mode: AmbientMode) -> None:
        self.previous_mode = self.mode
        self.mode = mode
        self.mode_elapsed = 0.0
        self.mode_duration = self._select_duration(mode)
        self.transition_progress = 0.0

    def _select_duration(self, mode: AmbientMode) -> float:
        low, high = self.config.mode_durations[tuple(AmbientMode).index(mode)]
        return self.rng.uniform(low, high)

    def _calculate_values(self, strength: float, blend: float) -> None:
        t = self.elapsed
        mode_scales = {
            AmbientMode.CALM: 0.55,
            AmbientMode.BREATHING: 1.0,
            AmbientMode.ENERGY_DRIFT: 0.85,
            AmbientMode.RING_RESONANCE: 0.9,
            AmbientMode.DEEP_IDLE: 0.38,
        }
        mode_scale = (
            mode_scales[self.previous_mode]
            + (mode_scales[self.mode] - mode_scales[self.previous_mode]) * blend
        )
        layered = math.sin(t * 0.47 + 0.4) * 0.62 + math.sin(t * 0.19 + 2.1) * 0.38
        slow = math.sin(t * 0.27 + 1.3)
        scale = strength * mode_scale
        self.values.glow_variation = layered * self.config.glow_limit * scale
        self.values.core_breathing = (layered * 0.7 + slow * 0.3) * self.config.breathing_limit * scale
        self.values.ring_drift = slow * self.config.ring_drift_limit * scale
        self.values.ring_wobble = layered * self.config.ring_wobble_degrees * scale
        self.values.particle_energy = layered * self.config.particle_energy_limit * scale
        self.values.particle_spread = slow * self.config.particle_spread_limit * scale
        self.values.highlight_variation = layered * self.config.highlight_limit * scale
        self.values.pulse_offset = slow * 0.08 * scale
