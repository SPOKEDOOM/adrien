from enum import Enum, auto


class PresenceState(Enum):
    BOOTING = auto()
    MATERIALIZING = auto()
    READY = auto()
    LISTENING = auto()
    THINKING = auto()
    PROCESSING = auto()
    SPEAKING = auto()
    IDLE = auto()
    ERROR = auto()
    DISSOLVING = auto()
