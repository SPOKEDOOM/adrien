from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QWidget
from app.core import PresenceState, PresenceStateManager
from app.ui.ai_core import AICore
from app.ui.sidebar import Sidebar
from app.ui.status_bar import AdrienStatusBar


class MainWindow(QMainWindow):
    DEVELOPMENT_STATE_CONTROLS = True

    def __init__(self):
        super().__init__()

        self.setWindowTitle("ADRIEN")
        self.resize(1400, 850)

        container = QWidget()

        layout = QHBoxLayout(container)

        self.sidebar = Sidebar()
        self.state_manager = PresenceStateManager(parent=self)
        self.core = AICore(self.state_manager)

        layout.addWidget(self.sidebar)
        layout.addWidget(self.core, 1)

        self.setCentralWidget(container)

        self.presence_status_bar = AdrienStatusBar()
        self.setStatusBar(self.presence_status_bar)
        self.state_manager.state_changed.connect(self._on_state_changed)
        self._on_state_changed(None, self.state_manager.current_state)
        self._state_shortcuts: list[QShortcut] = []
        self._install_state_shortcuts()

        QTimer.singleShot(500, self._begin_materialization)
        QTimer.singleShot(3700, self._become_ready)

    def _begin_materialization(self) -> None:
        self.state_manager.transition_to(PresenceState.MATERIALIZING)

    def _become_ready(self) -> None:
        self.state_manager.transition_to(PresenceState.READY)

    def _on_state_changed(self, previous_state, current_state) -> None:
        if self.DEVELOPMENT_STATE_CONTROLS:
            self.presence_status_bar.show_presence_state(current_state)

    def _install_state_shortcuts(self) -> None:
        if not self.DEVELOPMENT_STATE_CONTROLS:
            return
        states = tuple(PresenceState)
        for number, state in enumerate(states, start=1):
            shortcut = QShortcut(QKeySequence(str(number)), self)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.activated.connect(
                lambda selected_state=state: self.state_manager.transition_to_for_development(
                    selected_state
                )
            )
            self._state_shortcuts.append(shortcut)
