from enum import Enum, auto


class AdrienState(Enum):
    OFFLINE = auto()
    BOOTING = auto()
    MATERIALIZING = auto()
    READY = auto()
    LISTENING = auto()
    THINKING = auto()
    SPEAKING = auto()
    WORKING = auto()
    NOTIFYING = auto()
    DISSOLVING = auto()


class StateManager:

    def __init__(self):
        self.current_state = AdrienState.BOOTING

    def change_state(self, state: AdrienState):
        self.current_state = state

    def get_state(self):
        return self.current_state