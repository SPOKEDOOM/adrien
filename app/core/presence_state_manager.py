from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from app.core.presence_state import PresenceState

logger = logging.getLogger(__name__)


VALID_TRANSITIONS: dict[PresenceState, frozenset[PresenceState]] = {
    PresenceState.BOOTING: frozenset({PresenceState.MATERIALIZING}),
    PresenceState.MATERIALIZING: frozenset({PresenceState.READY}),
    PresenceState.READY: frozenset({PresenceState.LISTENING, PresenceState.SLEEP}),
    PresenceState.LISTENING: frozenset({PresenceState.THINKING, PresenceState.READY}),
    PresenceState.THINKING: frozenset({PresenceState.RESPONDING, PresenceState.READY}),
    PresenceState.RESPONDING: frozenset({PresenceState.READY, PresenceState.LISTENING}),
    PresenceState.SLEEP: frozenset({PresenceState.MATERIALIZING}),
}


class PresenceStateManager(QObject):
    """Owns operational state and validates all state transitions."""

    state_changed = Signal(object, object)

    def __init__(
        self,
        initial_state: PresenceState = PresenceState.BOOTING,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._current_state = initial_state
        self._previous_state: PresenceState | None = None

    @property
    def current_state(self) -> PresenceState:
        return self._current_state

    @property
    def previous_state(self) -> PresenceState | None:
        return self._previous_state

    def can_transition_to(self, state: PresenceState) -> bool:
        return state in VALID_TRANSITIONS[self._current_state]

    def transition_to(self, state: PresenceState) -> bool:
        if not isinstance(state, PresenceState):
            logger.debug("Rejected unknown presence state: %r", state)
            return False
        if state is self._current_state:
            logger.debug("Ignored duplicate presence state: %s", state.name)
            return False
        if not self.can_transition_to(state):
            logger.debug(
                "Rejected presence transition %s -> %s",
                self._current_state.name,
                state.name,
            )
            return False

        return self._apply_transition(state)

    def transition_to_for_development(self, state: PresenceState) -> bool:
        """Select any state for visual testing while preserving central ownership."""
        if not isinstance(state, PresenceState) or state is self._current_state:
            return False
        return self._apply_transition(state)

    def reset(self) -> bool:
        """Perform the single controlled transition outside the normal map."""
        if self._current_state is PresenceState.BOOTING:
            return False
        self._apply_transition(PresenceState.BOOTING)
        return True

    def _apply_transition(self, state: PresenceState) -> bool:
        previous = self._current_state
        self._previous_state = previous
        self._current_state = state
        print(f"Presence state: {previous.name} -> {state.name}", flush=True)
        self.state_changed.emit(previous, state)
        return True
