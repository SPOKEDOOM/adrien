from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QProgressBar, QPushButton, QWidget,
)

from app.core import PresenceState


class VoiceDebugPanel(QGroupBox):
    """Development diagnostics for real and typed voice paths."""

    def __init__(self, voice_manager):
        super().__init__("Voice Pipeline")
        self.voice_manager = voice_manager
        layout = QFormLayout(self)
        self.listening = QLabel("inactive")
        self.recognized = QLabel("—")
        self.reply = QLabel("—")
        self.speaking = QLabel("inactive")
        self.microphone = QComboBox()
        self.speaker = QComboBox()
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setTextVisible(False)
        self.rms = QLabel("0.00000")
        self.threshold = QLabel(f"{voice_manager.config.energy_threshold:.5f}")
        self.speech_detected = QLabel("no")
        self.recording_duration = QLabel("0.00 s")
        self.voice_backend = QLabel(voice_manager.microphone_backend)
        self.stt_backend = QLabel(voice_manager.stt_backend)
        self.tts_backend = QLabel(voice_manager.tts_backend)
        self.model_status = QLabel(
            "ready" if voice_manager.stt_backend != "placeholder" else "not installed"
        )
        self.transcription_status = QLabel("idle")
        self.status = QLabel("Ready")
        self.last_error = QLabel("—")
        self.start_button = QPushButton("Start Listening")
        self.stop_button = QPushButton("Stop and Transcribe")
        self.cancel_button = QPushButton("Cancel")
        self.stop_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        buttons = QWidget()
        button_layout = QHBoxLayout(buttons)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.cancel_button)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type placeholder speech")
        self._populate_devices()
        for label, widget in (
            ("Controls", buttons), ("Listening", self.listening),
            ("Input level", self.level), ("Live RMS", self.rms),
            ("Energy threshold", self.threshold),
            ("Speech detected", self.speech_detected),
            ("Recording duration", self.recording_duration),
            ("Recognized", self.recognized),
            ("Reply", self.reply), ("Speaking", self.speaking),
            ("Microphone", self.microphone), ("Speaker", self.speaker),
            ("Voice backend", self.voice_backend), ("STT backend", self.stt_backend),
            ("TTS backend", self.tts_backend), ("Model", self.model_status),
            ("Transcription", self.transcription_status), ("Status", self.status),
            ("Last error", self.last_error),
            ("Test input", self.input),
        ):
            layout.addRow(label, widget)
        self.start_button.clicked.connect(voice_manager.start_listening)
        self.stop_button.clicked.connect(voice_manager.stop_listening)
        self.cancel_button.clicked.connect(voice_manager.cancel)
        self.microphone.currentIndexChanged.connect(self._input_selected)
        self.speaker.currentIndexChanged.connect(self._output_selected)
        voice_manager.listening_changed.connect(self._listening_changed)
        voice_manager.recognized_text.connect(self.recognized.setText)
        voice_manager.reply_generated.connect(self.reply.setText)
        voice_manager.speaking_changed.connect(self._speaking_changed)
        voice_manager.level_changed.connect(lambda value: self.level.setValue(round(value * 100)))
        voice_manager.rms_changed.connect(lambda value: self.rms.setText(f"{value:.5f}"))
        voice_manager.speech_changed.connect(
            lambda detected: self.speech_detected.setText("yes" if detected else "no")
        )
        voice_manager.duration_changed.connect(
            lambda seconds: self.recording_duration.setText(f"{seconds:.2f} s")
        )
        voice_manager.status_changed.connect(self._status_changed)
        voice_manager.error.connect(self._show_error)
        voice_manager.state_manager.state_changed.connect(
            lambda old, new: self.start_button.setEnabled(
                new is PresenceState.READY and voice_manager.microphone_backend != "typed placeholder"
            )
        )
        self.start_button.setEnabled(
            voice_manager.state_manager.current_state is PresenceState.READY
            and voice_manager.microphone_backend != "typed placeholder"
        )
        if voice_manager.microphone_backend == "typed placeholder":
            self.status.setText("Microphone/STT dependencies unavailable; typed input active")
        self.input.returnPressed.connect(self._submit)

    def _populate_devices(self) -> None:
        controller = self.voice_manager.audio_controller
        self.microphone.addItem("System default", None)
        self.speaker.addItem("System default", None)
        for device in controller.input_devices():
            self.microphone.addItem(device.name, device.index)
        for device in controller.output_devices():
            self.speaker.addItem(device.name, device.index)

    def _input_selected(self) -> None:
        self.voice_manager.audio_controller.set_input_device(self.microphone.currentData())

    def _output_selected(self) -> None:
        self.voice_manager.audio_controller.set_output_device(self.speaker.currentData())

    def _listening_changed(self, active: bool) -> None:
        self.listening.setText("active" if active else "inactive")
        self.stop_button.setEnabled(active)
        self.cancel_button.setEnabled(active)

    def _speaking_changed(self, active: bool) -> None:
        self.speaking.setText("active" if active else "inactive")
        self.cancel_button.setEnabled(active)

    def _status_changed(self, message: str) -> None:
        self.transcription_status.setText(message)
        self.status.setText(message.capitalize())
        if message == "transcribing":
            self.model_status.setText("loading / transcribing")
            self.stop_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
        elif message == "model_loading":
            self.model_status.setText("loading")
        elif message == "model_ready":
            self.model_status.setText("ready")
        elif message == "complete":
            self.model_status.setText("ready")
        elif message == "error":
            self.model_status.setText("error")

    def _show_error(self, message: str) -> None:
        self.status.setText(message)
        self.transcription_status.setText("error")
        self.last_error.setText(message)

    def _submit(self) -> None:
        text = self.input.text().strip()
        if text and self.voice_manager.submit_debug_text(text):
            self.input.clear()
