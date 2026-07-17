from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QWidget
from app.core import PresenceState, PresenceStateManager
from app.ui.ai_core import AICore
from app.ui.sidebar import Sidebar
from app.ui.status_bar import AdrienStatusBar
from app.ui.voice_debug_panel import VoiceDebugPanel
from app.voice import VoiceManager


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
        self.voice_manager = VoiceManager(self.state_manager)
        self.core = AICore(self.state_manager)
        if self.DEVELOPMENT_STATE_CONTROLS:
            self.core.scene.materialization_seed = self.MATERIALIZATION_DEBUG_SEED

        layout.addWidget(self.sidebar)
        layout.addWidget(self.core, 1)
        self.voice_debug_panel = VoiceDebugPanel(self.voice_manager)
        self.voice_debug_panel.setVisible(self.DEVELOPMENT_STATE_CONTROLS)
        layout.addWidget(self.voice_debug_panel)

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
            self._show_ambient_status(current_state)

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
        listen = QShortcut(QKeySequence("V"), self)
        listen.setContext(Qt.WindowShortcut)
        listen.activated.connect(self.voice_manager.start_listening)
        self._state_shortcuts.append(listen)
        for key, callback in (
            ("A", self._toggle_ambient),
            ("B", self._cycle_ambient_mode),
            ("N", self._new_ambient_seed),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.activated.connect(callback)
            self._state_shortcuts.append(shortcut)

    def _show_ambient_status(self, state=None) -> None:
        controller = self.core.scene.ambient_controller
        self.presence_status_bar.show_ambient(
            state or self.state_manager.current_state,
            controller.enabled,
            controller.mode,
            controller.seed,
        )

    def _toggle_ambient(self) -> None:
        self.core.scene.ambient_controller.toggle()
        self._show_ambient_status()

    def _cycle_ambient_mode(self) -> None:
        self.core.scene.ambient_controller.cycle_mode()
        self._show_ambient_status()

    def _new_ambient_seed(self) -> None:
        self.core.scene.ambient_controller.reseed()
        self._show_ambient_status()
