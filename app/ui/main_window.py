from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QWidget
from app.core import PresenceState, PresenceStateManager
from app.ui.ai_core import AICore
from app.ui.sidebar import Sidebar
from app.ui.status_bar import AdrienStatusBar


class MainWindow(QMainWindow):
    DEVELOPMENT_STATE_CONTROLS = True
    MATERIALIZATION_DEBUG_SEED = 42

    def __init__(self):
        super().__init__()

        self.setWindowTitle("ADRIEN")
        self.resize(1400, 850)

        container = QWidget()

        layout = QHBoxLayout(container)

        self.sidebar = Sidebar()
        self.state_manager = PresenceStateManager(parent=self)
        self.core = AICore(self.state_manager)
        if self.DEVELOPMENT_STATE_CONTROLS:
            self.core.scene.materialization_seed = self.MATERIALIZATION_DEBUG_SEED

        layout.addWidget(self.sidebar)
        layout.addWidget(self.core, 1)

        self.setCentralWidget(container)

        self.presence_status_bar = AdrienStatusBar()
        self.setStatusBar(self.presence_status_bar)
        self.state_manager.state_changed.connect(self._on_state_changed)
        controller = self.core.scene.transition_controller
        controller.transition_started.connect(self._on_visual_transition_started)
        controller.transition_progress.connect(self._on_visual_transition_progress)
        controller.transition_completed.connect(self._on_visual_transition_completed)
        materialization = self.core.scene.materialization_controller
        materialization.progress_changed.connect(self._on_materialization_progress)
        self._on_state_changed(None, self.state_manager.current_state)
        self._state_shortcuts: list[QShortcut] = []
        self._install_state_shortcuts()

        QTimer.singleShot(500, self._begin_materialization)

    def _begin_materialization(self) -> None:
        self.state_manager.transition_to(PresenceState.MATERIALIZING)

    def _on_state_changed(self, previous_state, current_state) -> None:
        if self.DEVELOPMENT_STATE_CONTROLS:
            self.presence_status_bar.show_presence_state(current_state)

    def _on_visual_transition_started(self, source_state, target_state) -> None:
        self._show_visual_transition(0.0)

    def _on_visual_transition_progress(self, progress: float) -> None:
        self._show_visual_transition(progress)

    def _on_visual_transition_completed(self, target_state) -> None:
        if self.DEVELOPMENT_STATE_CONTROLS:
            self.presence_status_bar.show_presence_state(target_state)

    def _show_visual_transition(self, progress: float) -> None:
        if not self.DEVELOPMENT_STATE_CONTROLS:
            return
        controller = self.core.scene.transition_controller
        self.presence_status_bar.show_visual_transition(
            self.state_manager.current_state,
            controller.source_state,
            controller.target_state,
            progress,
        )

    def _on_materialization_progress(self, progress, phase) -> None:
        if self.DEVELOPMENT_STATE_CONTROLS:
            self.presence_status_bar.show_materialization(
                progress, phase, len(self.core.scene.particles),
                self.core.scene.active_materialization_seed,
            )

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
        replay = QShortcut(QKeySequence("M"), self)
        replay.setContext(Qt.WindowShortcut)
        replay.activated.connect(
            self.state_manager.replay_materialization_for_development
        )
        self._state_shortcuts.append(replay)
