from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QSplitter, QStackedWidget, QVBoxLayout, QWidget
from app.core import PresenceState, PresenceStateManager
from app.ui.ai_core import AICore
from app.ui.sidebar import Sidebar
from app.ui.status_bar import AdrienStatusBar
from app.ui.developer_tools_panel import DeveloperToolsPanel
from app.voice import VoiceManager
from app.wake import WakeManager
from app.settings import ApplicationSettings
from app.ui.settings_page import SettingsPage


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
        self.application_settings = ApplicationSettings(parent=self)
        ai_config = self.voice_manager.conversation_manager.ai_manager.config
        ai_config.allow_cloud_ai = self.application_settings.cloud_processing
        ai_config.default_backend = ("auto" if self.application_settings.default_provider == "automatic"
                                     else self.application_settings.default_provider)
        ai_config.provider_priority = self.application_settings.provider_priority
        ai_config.hybrid_mode = (self.application_settings.routing_mode
                                 if self.application_settings.default_provider == "automatic"
                                 else {"groq": "groq_only", "openai": "openai_only",
                                       "placeholder": "placeholder_only"}.get(
                                           self.application_settings.default_provider, "automatic"))
        self.wake_manager = WakeManager(
            self.state_manager, self.voice_manager, self.voice_manager.audio_controller
        )
        self.core = AICore(self.state_manager)
        if self.DEVELOPMENT_STATE_CONTROLS:
            self.core.scene.materialization_seed = self.MATERIALIZATION_DEBUG_SEED

        self.settings_page = SettingsPage(self.application_settings, self.voice_manager.conversation_manager)
        self.content_stack = QStackedWidget()
        self.sidebar_pages = {
            "Home": self.core,
            "Presence": self._information_page("Presence", "Presence state and ambient behavior are active. Runtime details are available in Developer Tools."),
            "Voice": self.settings_page.page("Voice"),
            "Brain": self._information_page("Brain", "Conversation, personality, and hybrid routing systems are active."),
            "Memory": self.settings_page.page("Memory"),
            "AI Providers": self.settings_page.page("AI Providers"),
            "Privacy": self.settings_page.page("Privacy"),
            "Developer": self.settings_page.page("Developer"),
            "About": self.settings_page.page("About"),
        }
        self.developer_tools_panel = DeveloperToolsPanel(
            self.wake_manager, self.voice_manager
        )
        for name in Sidebar.PAGE_NAMES: self.content_stack.addWidget(self.sidebar_pages[name])
        self.content_splitter = QSplitter(Qt.Horizontal)
        self.content_splitter.setObjectName("contentSplitter")
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.addWidget(self.content_stack)
        self.content_splitter.addWidget(self.developer_tools_panel)
        self.content_splitter.setStretchFactor(0, 1)
        self.content_splitter.setStretchFactor(1, 0)
        self.content_splitter.setSizes([1000, 380])
        self.developer_tools_panel.hide()
        layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)
        layout.addWidget(self.sidebar); layout.addWidget(self.content_splitter, 1)
        self.setCentralWidget(container)

        self.presence_status_bar = AdrienStatusBar()
        self.setStatusBar(self.presence_status_bar)
        self.sidebar.currentRowChanged.connect(self._sidebar_changed); self.sidebar.setCurrentRow(0)
        self.application_settings.changed.connect(self._setting_changed)
        self.settings_page.developer_mode_changed.connect(self._developer_mode_changed)
        self.settings_page.open_developer_tools_requested.connect(self.open_developer_tools)
        self.developer_tools_panel.close_requested.connect(self.close_developer_tools)
        self.voice_manager.error.connect(self.presence_status_bar.show_error)
        self.wake_manager.error.connect(self.presence_status_bar.show_error)
        self.state_manager.state_changed.connect(self._on_state_changed)
        controller = self.core.scene.transition_controller
        controller.transition_started.connect(self._on_visual_transition_started)
        controller.transition_progress.connect(self._on_visual_transition_progress)
        controller.transition_completed.connect(self._on_visual_transition_completed)
        materialization = self.core.scene.materialization_controller
        materialization.progress_changed.connect(self._on_materialization_progress)
        self._on_state_changed(None, self.state_manager.current_state)
        self._state_shortcuts: list[QShortcut] = []
        self._developer_tab_shortcuts: list[QShortcut] = []
        self._install_state_shortcuts()
        self._install_developer_tab_shortcuts()

        QTimer.singleShot(500, self._begin_materialization)
        self.wake_manager.start()
        self._developer_mode_changed(self.application_settings.developer_mode)
        self.developer_tools_panel.set_test_buttons_visible(self.application_settings.test_buttons)

    def _sidebar_changed(self, row: int) -> None:
        if 0 <= row < self.content_stack.count():
            self.content_stack.setCurrentIndex(row)
            if row != 0:
                self.close_developer_tools()

    @staticmethod
    def _information_page(title: str, description: str) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(32, 32, 32, 32)
        heading = QLabel(title); heading.setStyleSheet("font-size:22px; font-weight:600; color:#8ed8ff;")
        detail = QLabel(description); detail.setWordWrap(True)
        layout.addWidget(heading); layout.addWidget(detail); layout.addStretch(); return page

    def _setting_changed(self, key: str, value) -> None:
        config = self.voice_manager.conversation_manager.ai_manager.config
        if key == "privacy/cloud_processing":
            self.voice_manager.conversation_manager.set_cloud_ai_allowed(bool(value))
        elif key == "ai/default_provider":
            config.default_backend = "auto" if value == "automatic" else str(value)
            mode = (self.application_settings.routing_mode if value == "automatic" else
                    {"groq": "groq_only", "openai": "openai_only",
                     "placeholder": "placeholder_only"}.get(str(value), "automatic"))
            self.voice_manager.conversation_manager.set_hybrid_mode(mode)
        elif key == "ai/provider_priority":
            config.provider_priority = self.application_settings.provider_priority
        elif key == "ai/routing_mode" and self.application_settings.default_provider == "automatic":
            self.voice_manager.conversation_manager.set_hybrid_mode(str(value))
        elif key == "developer/test_buttons":
            self.developer_tools_panel.set_test_buttons_visible(bool(value))

    def _developer_mode_changed(self, enabled: bool) -> None:
        self.settings_page.open_developer_tools.setEnabled(enabled)
        if not enabled:
            self.close_developer_tools()

    def _begin_materialization(self) -> None:
        self.state_manager.transition_to(PresenceState.MATERIALIZING)

    def _on_state_changed(self, previous_state, current_state) -> None:
        self.presence_status_bar.show_presence_state(current_state)

    def _on_visual_transition_started(self, source_state, target_state) -> None:
        pass

    def _on_visual_transition_progress(self, progress: float) -> None:
        pass

    def _on_visual_transition_completed(self, target_state) -> None:
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
        pass

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
        developer_tools = QShortcut(QKeySequence("F12"), self)
        developer_tools.setContext(Qt.WindowShortcut)
        developer_tools.activated.connect(self.toggle_developer_tools)
        self._state_shortcuts.append(developer_tools)
        simulate_wake = QShortcut(QKeySequence("Ctrl+Space"), self)
        simulate_wake.setContext(Qt.WindowShortcut)
        simulate_wake.activated.connect(lambda: self.wake_manager.simulate(0.95))
        self._state_shortcuts.append(simulate_wake)
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

    def toggle_developer_tools(self) -> None:
        if not self.application_settings.developer_mode:
            return
        if self.developer_tools_panel.isVisible():
            self.close_developer_tools()
        else:
            self.open_developer_tools()

    def open_developer_tools(self) -> None:
        if not self.application_settings.developer_mode:
            return
        self.sidebar.setCurrentRow(0)
        self.content_stack.setCurrentWidget(self.core)
        self.developer_tools_panel.show()
        self.content_splitter.setSizes([max(1, self.content_splitter.width() - 380), 380])
        self.developer_tools_panel.raise_()
        self.developer_tools_panel.setFocus(Qt.OtherFocusReason)
        self._set_developer_shortcuts_enabled(True)

    def close_developer_tools(self) -> None:
        self.developer_tools_panel.hide()
        self._set_developer_shortcuts_enabled(False)

    def _install_developer_tab_shortcuts(self) -> None:
        for index in range(4):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{index + 1}"), self)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.activated.connect(
                lambda selected=index: self.developer_tools_panel.tabs.setCurrentIndex(selected)
            )
            shortcut.setEnabled(False)
            self._developer_tab_shortcuts.append(shortcut)

    def _set_developer_shortcuts_enabled(self, visible: bool) -> None:
        for shortcut in self._developer_tab_shortcuts:
            shortcut.setEnabled(visible)

    def closeEvent(self, event) -> None:
        self.wake_manager.shutdown()
        self.voice_manager.shutdown()
        super().closeEvent(event)
