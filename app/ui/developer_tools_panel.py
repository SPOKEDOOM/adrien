from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


class DeveloperToolsPanel(QScrollArea):
    """One compact, scrollable home for non-production controls and diagnostics."""

    def __init__(self, wake_manager, voice_manager) -> None:
        super().__init__()
        self.wake_manager = wake_manager
        self.voice_manager = voice_manager
        self.setWidgetResizable(True)
        self.setMinimumWidth(320)
        self.setMaximumWidth(380)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.addWidget(self._wake_section())
        layout.addWidget(self._voice_section())
        layout.addWidget(self._diagnostics_section())
        layout.addStretch(1)
        self.setWidget(content)
        self._connect_updates()

    @staticmethod
    def _button_row(*buttons) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        for button in buttons:
            row.addWidget(button)
        return widget

    def _wake_section(self) -> QGroupBox:
        section = QGroupBox("Wake Engine")
        layout = QVBoxLayout(section)
        self.wake_start = QPushButton("Start")
        self.wake_stop = QPushButton("Stop")
        self.simulate_wake = QPushButton("Simulate Wake")
        self.simulate_low = QPushButton("Low 0.40")
        self.simulate_high = QPushButton("High 0.95")
        layout.addWidget(self._button_row(self.wake_start, self.wake_stop))
        layout.addWidget(self.simulate_wake)
        layout.addWidget(self._button_row(self.simulate_low, self.simulate_high))
        self.wake_start.clicked.connect(self.wake_manager.start)
        self.wake_stop.clicked.connect(self.wake_manager.stop)
        self.simulate_wake.clicked.connect(lambda: self.wake_manager.simulate(0.95))
        self.simulate_low.clicked.connect(lambda: self.wake_manager.simulate(0.40))
        self.simulate_high.clicked.connect(lambda: self.wake_manager.simulate(0.95))
        return section

    def _voice_section(self) -> QGroupBox:
        section = QGroupBox("Voice")
        layout = QVBoxLayout(section)
        self.voice_start = QPushButton("Start Listening")
        self.voice_stop = QPushButton("Stop and Transcribe")
        self.voice_cancel = QPushButton("Cancel")
        layout.addWidget(self.voice_start)
        layout.addWidget(self._button_row(self.voice_stop, self.voice_cancel))
        self.test_input = QLineEdit()
        self.test_input.setPlaceholderText("Typed test input")
        layout.addWidget(self.test_input)
        self.voice_start.clicked.connect(self.voice_manager.start_listening)
        self.voice_stop.clicked.connect(self.voice_manager.stop_listening)
        self.voice_cancel.clicked.connect(self.voice_manager.cancel)
        self.test_input.returnPressed.connect(self._submit_text)
        return section

    def _diagnostics_section(self) -> QGroupBox:
        section = QGroupBox("Diagnostics")
        layout = QFormLayout(section)
        self.backend_selector = QComboBox()
        self.backend_selector.addItem("Development fallback", "development")
        self.backend = QLabel(self.wake_manager.backend_name)
        self.microphone = QComboBox()
        self.microphone.addItem("System default", None)
        for device in self.voice_manager.audio_controller.input_devices():
            self.microphone.addItem(device.name, device.index)
        self.audio_mode = QLabel(self.voice_manager.audio_controller.mode.name)
        self.confidence = QLabel("—")
        self.threshold = QLabel(f"{self.wake_manager.config.wake_confidence_threshold:.2f}")
        self.last_error = QLabel("—")
        self.recognized = QLabel("—")
        self.reply = QLabel("—")
        for label, widget in (
            ("Backend selection", self.backend_selector), ("Backend", self.backend),
            ("Microphone", self.microphone), ("Audio mode", self.audio_mode),
            ("Confidence", self.confidence), ("Threshold", self.threshold),
            ("Last error", self.last_error), ("Recognized", self.recognized),
            ("Reply", self.reply),
        ):
            layout.addRow(label, widget)
        self.microphone.currentIndexChanged.connect(
            lambda: self.voice_manager.audio_controller.set_input_device(
                self.microphone.currentData()
            )
        )
        return section

    def _connect_updates(self) -> None:
        self.wake_manager.backend_changed.connect(self.backend.setText)
        self.wake_manager.candidate_evaluated.connect(
            lambda result, accepted, reason: self.confidence.setText(f"{result.confidence:.2f}")
        )
        self.wake_manager.error.connect(self.last_error.setText)
        self.voice_manager.error.connect(self.last_error.setText)
        self.voice_manager.recognized_text.connect(self.recognized.setText)
        self.voice_manager.reply_generated.connect(self.reply.setText)
        self.voice_manager.listening_changed.connect(self._listening_changed)
        self.voice_manager.state_manager.state_changed.connect(
            lambda old, new: self.audio_mode.setText(
                self.voice_manager.audio_controller.mode.name
            )
        )

    def _listening_changed(self, active: bool) -> None:
        self.voice_stop.setEnabled(active)
        self.voice_cancel.setEnabled(active)
        self.audio_mode.setText(self.voice_manager.audio_controller.mode.name)

    def _submit_text(self) -> None:
        text = self.test_input.text().strip()
        if text and self.voice_manager.submit_debug_text(text):
            self.test_input.clear()
