from enum import Enum, auto


class PresenceState(Enum):
    """Operational states supported by ADRIEN's visual presence."""

    BOOTING = auto()
    MATERIALIZING = auto()
    READY = auto()
    LISTENING = auto()
    THINKING = auto()
    RESPONDING = auto()
    SLEEP = auto()
