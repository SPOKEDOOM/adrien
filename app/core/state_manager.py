"""Backward-compatible exports for the centralized presence state system."""

from app.core.presence_state import PresenceState
from app.core.presence_state_manager import PresenceStateManager, VALID_TRANSITIONS

__all__ = ["PresenceState", "PresenceStateManager", "VALID_TRANSITIONS"]
