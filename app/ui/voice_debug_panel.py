from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QLineEdit


class VoiceDebugPanel(QGroupBox):
    """Development diagnostics and text injection for the placeholder backend."""

    def __init__(self, voice_manager):
        super().__init__("Voice Pipeline")
        self.voice_manager = voice_manager
        layout = QFormLayout(self)
        self.listening = QLabel("inactive")
        self.recognized = QLabel("—")
        self.reply = QLabel("—")
        self.speaking = QLabel("inactive")
        self.microphone = QLabel(voice_manager.audio_controller.input_device)
        self.speaker = QLabel(voice_manager.audio_controller.output_device)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type placeholder speech while listening")
        layout.addRow("Listening", self.listening)
        layout.addRow("Recognized", self.recognized)
        layout.addRow("Reply", self.reply)
        layout.addRow("Speaking", self.speaking)
        layout.addRow("Microphone", self.microphone)
        layout.addRow("Speaker", self.speaker)
        layout.addRow("Test input", self.input)
        voice_manager.listening_changed.connect(
            lambda active: self.listening.setText("active" if active else "inactive")
        )
        voice_manager.recognized_text.connect(self.recognized.setText)
        voice_manager.reply_generated.connect(self.reply.setText)
        voice_manager.speaking_changed.connect(
            lambda active: self.speaking.setText("active" if active else "inactive")
        )
        voice_manager.error.connect(lambda message: self.listening.setText(f"Error: {message}"))
        self.input.returnPressed.connect(self._submit)

    def _submit(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        if self.voice_manager.submit_debug_text(text):
            self.input.clear()
