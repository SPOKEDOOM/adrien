from __future__ import annotations

from dataclasses import fields
from enum import Enum

from PySide6.QtCore import QObject, Signal

from app.core.presence_state import PresenceState
from app.rendering.profiles import AnimationProfile, profile_for


class Easing(Enum):
    SMOOTHSTEP = "smoothstep"
    EASE_IN_OUT_CUBIC = "ease_in_out_cubic"
    EASE_OUT_CUBIC = "ease_out_cubic"


DEFAULT_TRANSITION_DURATION = 0.7

TRANSITION_DURATIONS: dict[tuple[PresenceState, PresenceState], float] = {
    (PresenceState.BOOTING, PresenceState.MATERIALIZING): 1.2,
    (PresenceState.MATERIALIZING, PresenceState.READY): 1.5,
    (PresenceState.READY, PresenceState.LISTENING): 0.35,
    (PresenceState.LISTENING, PresenceState.THINKING): 0.6,
    (PresenceState.THINKING, PresenceState.RESPONDING): 0.45,
    (PresenceState.RESPONDING, PresenceState.READY): 0.8,
    (PresenceState.READY, PresenceState.SLEEP): 1.8,
    (PresenceState.SLEEP, PresenceState.MATERIALIZING): 1.4,
}

TRANSITION_EASING: dict[tuple[PresenceState, PresenceState], Easing] = {
    (PresenceState.READY, PresenceState.LISTENING): Easing.EASE_OUT_CUBIC,
    (PresenceState.LISTENING, PresenceState.THINKING): Easing.EASE_IN_OUT_CUBIC,
    (PresenceState.THINKING, PresenceState.RESPONDING): Easing.EASE_OUT_CUBIC,
    (PresenceState.RESPONDING, PresenceState.READY): Easing.SMOOTHSTEP,
    (PresenceState.READY, PresenceState.SLEEP): Easing.SMOOTHSTEP,
    (PresenceState.SLEEP, PresenceState.MATERIALIZING): Easing.EASE_IN_OUT_CUBIC,
    (PresenceState.BOOTING, PresenceState.MATERIALIZING): Easing.SMOOTHSTEP,
    (PresenceState.MATERIALIZING, PresenceState.READY): Easing.SMOOTHSTEP,
}

PROFILE_FIELDS = tuple(field.name for field in fields(AnimationProfile))


def eased_progress(progress: float, easing: Easing) -> float:
    value = max(0.0, min(1.0, progress))
    if easing is Easing.EASE_OUT_CUBIC:
        return 1.0 - (1.0 - value) ** 3
    if easing is Easing.EASE_IN_OUT_CUBIC:
        if value < 0.5:
            return 4.0 * value**3
        return 1.0 - ((-2.0 * value + 2.0) ** 3) / 2.0
    return value * value * (3.0 - 2.0 * value)


class StateTransitionController(QObject):
    """Blends visual profiles independently from operational state validation."""

    transition_started = Signal(object, object)
    transition_progress = Signal(float)
    transition_completed = Signal(object)

    def __init__(self, initial_state: PresenceState, parent: QObject | None = None):
        super().__init__(parent)
        initial = profile_for(initial_state)
        self.current_profile = AnimationProfile(**{
            name: getattr(initial, name) for name in PROFILE_FIELDS
        })
        self._source_profile = AnimationProfile(**{
            name: getattr(initial, name) for name in PROFILE_FIELDS
        })
        self._target_profile = initial
        self.source_state = initial_state
        self.target_state = initial_state
        self.progress = 1.0
        self.duration = 0.0
        self.elapsed = 0.0
        self.easing = Easing.SMOOTHSTEP
        self.entry_accent = 0.0
        self.is_active = False

    def transition_to(self, state: PresenceState) -> bool:
        if state is self.target_state:
            return False

        previous_target = self.target_state
        self.source_state = previous_target
        self.target_state = state
        self._copy_profile(self.current_profile, self._source_profile)
        self._target_profile = profile_for(state)
        key = (previous_target, state)
        self.duration = TRANSITION_DURATIONS.get(key, DEFAULT_TRANSITION_DURATION)
        self.easing = TRANSITION_EASING.get(key, Easing.SMOOTHSTEP)
        self.elapsed = 0.0
        self.progress = 0.0
        self.entry_accent = 1.0
        self.is_active = True
        print(
            f"Visual transition started: {previous_target.name} -> {state.name}",
            flush=True,
        )
        self.transition_started.emit(previous_target, state)
        self.transition_progress.emit(0.0)
        return True

    def update(self, delta_seconds: float) -> None:
        self.entry_accent = max(0.0, self.entry_accent - max(0.0, delta_seconds) / 0.7)
        if not self.is_active:
            return

        self.elapsed += max(0.0, delta_seconds)
        self.progress = min(1.0, self.elapsed / self.duration)
        blend = eased_progress(self.progress, self.easing)
        for name in PROFILE_FIELDS:
            source = getattr(self._source_profile, name)
            target = getattr(self._target_profile, name)
            setattr(self.current_profile, name, source + (target - source) * blend)
        self.transition_progress.emit(self.progress)

        if self.progress >= 1.0:
            self.is_active = False
            print(f"Visual transition completed: {self.target_state.name}", flush=True)
            self.transition_completed.emit(self.target_state)

    @staticmethod
    def _copy_profile(source: AnimationProfile, target: AnimationProfile) -> None:
        for name in PROFILE_FIELDS:
            setattr(target, name, getattr(source, name))
