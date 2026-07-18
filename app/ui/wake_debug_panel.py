from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QWidget


class WakeDebugPanel(QGroupBox):
    """Development-only controls and diagnostics for the Wake Engine."""

    def __init__(self, wake_manager) -> None:
        super().__init__("Wake Engine")
        self.wake_manager = wake_manager
        layout = QFormLayout(self)
        self.backend = QLabel(wake_manager.backend_name)
        self.engine_status = QLabel("stopped")
        self.monitoring = QLabel("no")
        self.phrase = QLabel(wake_manager.config.wake_phrase)
        self.threshold = QLabel(f"{wake_manager.config.wake_confidence_threshold:.2f}")
        self.last_phrase = QLabel("—")
        self.last_confidence = QLabel("—")
        self.last_timestamp = QLabel("—")
        self.cooldown = QLabel("0.0 s")
        self.audio_mode = QLabel(wake_manager.audio_controller.mode.name)
        self.command_timeout = QLabel("0.0 s")
        self.last_error = QLabel("—")
        controls = QWidget()
        row = QHBoxLayout(controls)
        row.setContentsMargins(0, 0, 0, 0)
        self.start_button = QPushButton("Start Wake Engine")
        self.stop_button = QPushButton("Stop Wake Engine")
        self.simulate_button = QPushButton("Simulate Wake")
        self.low_button = QPushButton("Confidence 0.40")
        self.high_button = QPushButton("Confidence 0.95")
        self.sleep_button = QPushButton("Force Sleep")
        self.force_button = QPushButton("Force Wake Sequence")
        for button in (self.start_button, self.stop_button, self.simulate_button,
                       self.low_button, self.high_button, self.sleep_button, self.force_button):
            row.addWidget(button)
        for label, widget in (
            ("Controls", controls), ("Backend", self.backend), ("Status", self.engine_status),
            ("Monitoring active", self.monitoring), ("Wake phrase", self.phrase),
            ("Confidence threshold", self.threshold), ("Last phrase", self.last_phrase),
            ("Last confidence", self.last_confidence), ("Last wake timestamp", self.last_timestamp),
            ("Cooldown remaining", self.cooldown), ("Audio ownership", self.audio_mode),
            ("Command timeout", self.command_timeout), ("Last error", self.last_error),
        ):
            layout.addRow(label, widget)
        self.start_button.clicked.connect(wake_manager.start)
        self.stop_button.clicked.connect(wake_manager.stop)
        self.simulate_button.clicked.connect(lambda: wake_manager.simulate(0.95))
        self.low_button.clicked.connect(lambda: wake_manager.simulate(0.40))
        self.high_button.clicked.connect(lambda: wake_manager.simulate(0.95))
        self.sleep_button.clicked.connect(wake_manager.force_sleep)
        self.force_button.clicked.connect(wake_manager.force_wake_sequence)
        wake_manager.status_changed.connect(self.engine_status.setText)
        wake_manager.monitoring_changed.connect(
            lambda active: self.monitoring.setText("yes" if active else "no")
        )
        wake_manager.backend_changed.connect(self.backend.setText)
        wake_manager.candidate_evaluated.connect(self._candidate)
        wake_manager.cooldown_changed.connect(lambda value: self.cooldown.setText(f"{value:.1f} s"))
        wake_manager.command_timeout_changed.connect(
            lambda value: self.command_timeout.setText(f"{value:.1f} s")
        )
        wake_manager.error.connect(self.last_error.setText)
        self._mode_timer = QTimer(self)
        self._mode_timer.timeout.connect(
            lambda: self.audio_mode.setText(wake_manager.audio_controller.mode.name)
        )
        self._mode_timer.start(100)

    def _candidate(self, result, accepted: bool, reason: str) -> None:
        self.last_phrase.setText(result.phrase)
        self.last_confidence.setText(f"{result.confidence:.2f}")
        self.last_timestamp.setText(result.timestamp.astimezone().strftime("%H:%M:%S"))
        if not accepted:
            self.engine_status.setText(f"rejected: {reason}")
