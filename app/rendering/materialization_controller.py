from __future__ import annotations

from enum import Enum, auto

from PySide6.QtCore import QObject, Signal


class MaterializationPhase(Enum):
    FADE_IN = auto()
    CONVERGENCE = auto()
    CORE_FORMATION = auto()
    STABILIZATION = auto()
    COMPLETE = auto()


PHASE_DURATIONS: dict[MaterializationPhase, float] = {
    MaterializationPhase.FADE_IN: 0.45,
    MaterializationPhase.CONVERGENCE: 1.15,
    MaterializationPhase.CORE_FORMATION: 0.9,
    MaterializationPhase.STABILIZATION: 0.7,
}

ACTIVE_PHASES = tuple(PHASE_DURATIONS)
TOTAL_MATERIALIZATION_DURATION = sum(PHASE_DURATIONS.values())


class MaterializationController(QObject):
    """Tracks the lightweight cinematic assembly sequence."""

    started = Signal()
    progress_changed = Signal(float, object)
    completed = Signal()
    cancelled = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.progress = 0.0
        self.phase = MaterializationPhase.FADE_IN
        self.phase_progress = 0.0
        self.elapsed = 0.0
        self.is_active = False
        self.is_complete = False

    def start(self) -> bool:
        self.progress = 0.0
        self.phase = MaterializationPhase.FADE_IN
        self.phase_progress = 0.0
        self.elapsed = 0.0
        self.is_active = True
        self.is_complete = False
        self.started.emit()
        self.progress_changed.emit(0.0, self.phase)
        return True

    def update(self, delta_seconds: float) -> None:
        if not self.is_active:
            return
        self.elapsed = min(
            TOTAL_MATERIALIZATION_DURATION,
            self.elapsed + max(0.0, delta_seconds),
        )
        self.progress = min(1.0, self.elapsed / TOTAL_MATERIALIZATION_DURATION)
        self._update_phase()
        self.progress_changed.emit(self.progress, self.phase)
        if self.elapsed >= TOTAL_MATERIALIZATION_DURATION:
            self.is_active = False
            self.is_complete = True
            self.phase = MaterializationPhase.COMPLETE
            self.phase_progress = 1.0
            self.progress = 1.0
            self.progress_changed.emit(1.0, self.phase)
            self.completed.emit()

    def cancel(self) -> bool:
        if not self.is_active:
            return False
        self.is_active = False
        self.is_complete = False
        self.cancelled.emit()
        return True

    def _update_phase(self) -> None:
        phase_start = 0.0
        for phase in ACTIVE_PHASES:
            duration = PHASE_DURATIONS[phase]
            phase_end = phase_start + duration
            if self.elapsed < phase_end or phase is ACTIVE_PHASES[-1]:
                self.phase = phase
                self.phase_progress = max(
                    0.0,
                    min(1.0, (self.elapsed - phase_start) / duration),
                )
                return
            phase_start = phase_end
