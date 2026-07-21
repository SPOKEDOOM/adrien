from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QTabWidget, QToolButton, QVBoxLayout, QWidget,
)


class DeveloperToolsPanel(QWidget):
    """Compact tabbed developer workspace with no outer scrolling surface."""

    TAB_NAMES = ("Voice", "Wake", "Conversation", "Diagnostics")
    close_requested = Signal()

    def __init__(self, wake_manager, voice_manager) -> None:
        super().__init__()
        self.wake_manager = wake_manager
        self.voice_manager = voice_manager
        self.setObjectName("developerToolsPanel")
        self.setMinimumWidth(340)
        self.setMaximumWidth(480)
        self.setMinimumHeight(560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(6)
        header = QWidget(); header.setObjectName("developerToolsHeader")
        header_layout = QHBoxLayout(header); header_layout.setContentsMargins(4, 0, 0, 0)
        title = QLabel("Developer Tools"); title.setObjectName("developerToolsTitle")
        self.close_button = QToolButton(); self.close_button.setText("×")
        self.close_button.setObjectName("developerToolsClose")
        self.close_button.setToolTip("Close Developer Tools")
        self.close_button.setAutoRaise(True); self.close_button.setFixedSize(28, 28)
        header_layout.addWidget(title); header_layout.addStretch(); header_layout.addWidget(self.close_button)
        layout.addWidget(header)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs)
        self.tabs.addTab(self._voice_tab(), "Voice")
        self.tabs.addTab(self._wake_tab(), "Wake")
        self.tabs.addTab(self._conversation_tab(), "Conversation")
        self.tabs.addTab(self._diagnostics_tab(), "Diagnostics")
        self.close_button.clicked.connect(self.close_requested)
        self.setStyleSheet("""
            QWidget#developerToolsPanel { background:#10151d; border-left:1px solid #2a3d50; }
            QWidget#developerToolsHeader { border-bottom:1px solid #263648; }
            QLabel#developerToolsTitle { color:#8ed8ff; font-size:15px; font-weight:600; }
            QToolButton#developerToolsClose { color:#dce8f5; font-size:20px; border-radius:4px; }
            QToolButton#developerToolsClose:hover { background:#293847; }
        """)
        self._connect_updates()
        self._conversation_diagnostics(
            self.voice_manager.conversation_manager.diagnostics_snapshot()
        )

    @staticmethod
    def _button_row(*buttons) -> QWidget:
        widget = QWidget(); row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0); row.setSpacing(5)
        for button in buttons:
            button.setMaximumHeight(28); row.addWidget(button)
        return widget

    @staticmethod
    def _form(widget: QWidget) -> QFormLayout:
        form = QFormLayout(widget)
        form.setContentsMargins(8, 8, 8, 8)
        form.setHorizontalSpacing(8); form.setVerticalSpacing(6)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        return form

    @staticmethod
    def _readonly(text="—", height=28) -> QLineEdit:
        field = QLineEdit(text); field.setReadOnly(True); field.setMaximumHeight(height)
        field.setToolTip(text)
        return field

    @staticmethod
    def _set_field(field, text) -> None:
        value = str(text)
        field.setText(value); field.setToolTip(value)

    def _voice_tab(self) -> QWidget:
        tab = QWidget(); form = self._form(tab)
        self.voice_start = QPushButton("Start Listening")
        self.voice_stop = QPushButton("Stop & Transcribe")
        self.voice_cancel = QPushButton("Cancel")
        self.microphone = QComboBox(); self.microphone.setMaximumHeight(28)
        self.microphone.addItem("System default", None)
        for device in self.voice_manager.audio_controller.input_devices():
            self.microphone.addItem(device.name, device.index)
        self.input_level = self._readonly("0.00000")
        self.recognized = self._readonly()
        self.reply = self._readonly()
        self.test_input = QLineEdit(); self.test_input.setMaximumHeight(28)
        self.test_input.setPlaceholderText("Typed test input")
        form.addRow(self._button_row(self.voice_start, self.voice_stop, self.voice_cancel))
        form.addRow("Microphone", self.microphone); form.addRow("Input level", self.input_level)
        form.addRow("Recognized", self.recognized); form.addRow("Last reply", self.reply)
        form.addRow("Test input", self.test_input)
        self.voice_start.clicked.connect(self.voice_manager.start_listening)
        self.voice_stop.clicked.connect(self.voice_manager.stop_listening)
        self.voice_cancel.clicked.connect(self.voice_manager.cancel)
        self.microphone.currentIndexChanged.connect(
            lambda: self.voice_manager.audio_controller.set_input_device(self.microphone.currentData())
        )
        self.test_input.returnPressed.connect(self._submit_text)
        return tab

    def _wake_tab(self) -> QWidget:
        tab = QWidget(); form = self._form(tab)
        self.wake_start = QPushButton("Start Wake")
        self.wake_stop = QPushButton("Stop Wake")
        self.simulate_wake = QPushButton("Simulate Wake")
        self.force_sleep = QPushButton("Force Sleep")
        self.simulate_low = QPushButton("Test 0.40")
        self.simulate_high = QPushButton("Test 0.95")
        self.backend_selector = QComboBox(); self.backend_selector.addItem("Development fallback", "development")
        self.backend = self._readonly(self.wake_manager.backend_name)
        self.confidence = self._readonly()
        self.wake_status = self._readonly("running" if self.wake_manager.running else "stopped")
        form.addRow(self._button_row(self.wake_start, self.wake_stop))
        form.addRow(self._button_row(self.simulate_wake, self.force_sleep))
        form.addRow("Backend selection", self.backend_selector)
        form.addRow("Backend", self.backend); form.addRow("Last confidence", self.confidence)
        form.addRow("Wake status", self.wake_status)
        form.addRow("Confidence tests", self._button_row(self.simulate_low, self.simulate_high))
        self.wake_start.clicked.connect(self.wake_manager.start); self.wake_stop.clicked.connect(self.wake_manager.stop)
        self.simulate_wake.clicked.connect(lambda: self.wake_manager.simulate(.95))
        self.force_sleep.clicked.connect(self.wake_manager.force_sleep)
        self.simulate_low.clicked.connect(lambda: self.wake_manager.simulate(.40))
        self.simulate_high.clicked.connect(lambda: self.wake_manager.simulate(.95))
        return tab

    def _conversation_tab(self) -> QWidget:
        tab = QWidget(); form = self._form(tab)
        manager = self.voice_manager.conversation_manager
        self.hybrid_mode = QComboBox(); self.hybrid_mode.addItems(manager.ai_manager.router.MODES)
        self.hybrid_mode.setCurrentText(manager.ai_manager.config.hybrid_mode)
        self.selected_backend = self._readonly("none")
        self.local_backend_status = self._readonly("unavailable")
        self.openai_backend_status = self._readonly("unavailable")
        self.openai_model = self._readonly("not configured")
        self.openai_api_key = self._readonly("missing")
        self.openai_environment_detected = self._readonly("no")
        self.openai_sdk_installed = self._readonly("no")
        self.openai_backend_enabled = self._readonly("no")
        self.cloud_ai_status = self._readonly("allowed")
        self.cloud_ai_allowed = QCheckBox("Allow cloud processing")
        self.cloud_ai_allowed.setChecked(manager.ai_manager.config.allow_cloud_ai)
        self.openai_response_id = self._readonly()
        self.openai_latency = self._readonly("0.000 s")
        self.openai_usage = self._readonly()
        self.openai_error_category = self._readonly()
        self.groq_backend_status = self._readonly("unavailable")
        self.groq_model = self._readonly("not configured"); self.groq_api_key = self._readonly("missing")
        self.groq_environment_detected = self._readonly("no"); self.groq_sdk_installed = self._readonly("no")
        self.groq_backend_enabled = self._readonly("no"); self.groq_response_id = self._readonly()
        self.groq_latency = self._readonly("0.000 s"); self.groq_usage = self._readonly(); self.groq_error = self._readonly()
        self.placeholder_backend_status = self._readonly("available")
        self.last_backend_used = self._readonly("none")
        self.fallback_used = self._readonly("no")
        self.ai_last_error = self._readonly()
        self.current_personality = self._readonly(manager.personality_manager.profile.name)
        self.reload_personality = QPushButton("Reload Personality")
        self.preview_personality_prompt = QPushButton("Preview System Prompt")
        self.conversation_backend = self._readonly(manager.backend_name)
        self.conversation_status = self._readonly(manager.backend_status)
        self.conversation_input = self._readonly()
        self.conversation_reply = self._readonly()
        self.conversation_count = self._readonly("0")
        self.conversation_time = self._readonly("0.000 s")
        self.memory_recent_messages = self._readonly("0")
        self.memory_summary_exists = self._readonly("no")
        self.memory_summary_size = self._readonly("0")
        self.memory_summary_updated = self._readonly("—")
        self.memory_messages_summarized = self._readonly("0")
        self.memory_estimated_tokens = self._readonly("0")
        self.memory_status = self._readonly("Ready")
        self.view_memory_summary = QPushButton("View Summary")
        self.force_memory_summary = QPushButton("Force Summary")
        self.clear_conversation_memory = QPushButton("Clear Conversation Memory")
        self.long_term_enabled = self._readonly("yes")
        self.long_term_storage = self._readonly("available")
        self.long_term_total = self._readonly("0"); self.long_term_enabled_count = self._readonly("0")
        self.long_term_pending = self._readonly("0"); self.long_term_last_saved = self._readonly("—")
        self.long_term_retrieval_count = self._readonly("0"); self.long_term_retrieval_latency = self._readonly("0.000 s")
        self.refresh_long_term = QPushButton("Refresh Memory Diagnostics")
        self.rebuild_memory_index = QPushButton("Rebuild Memory Index")
        self.view_memory_storage_path = QPushButton("View Storage Path")
        self.clear_pending_memories = QPushButton("Clear Pending Candidates")
        self.clear_conversation = QPushButton("Clear Conversation History")
        self.test_local = QPushButton("Test Local"); self.test_openai = QPushButton("Test OpenAI")
        self.test_groq = QPushButton("Test Groq")
        self.test_placeholder = QPushButton("Test Placeholder")
        self.run_hybrid_test = QPushButton("Run Hybrid Test"); self.cancel_ai_request = QPushButton("Cancel Request")
        self.clear_conversation.setMaximumHeight(28)
        form.addRow("Selected", self.selected_backend)
        form.addRow("Local / OpenAI", self._button_row(self.local_backend_status, self.openai_backend_status))
        form.addRow("Groq", self.groq_backend_status)
        form.addRow("Cloud / response", self._button_row(self.cloud_ai_status, self.openai_response_id))
        form.addRow("Latency / error", self._button_row(self.openai_latency, self.openai_error_category))
        form.addRow("OpenAI usage", self.openai_usage)
        form.addRow("Groq response", self.groq_response_id)
        form.addRow("Groq latency / error", self._button_row(self.groq_latency, self.groq_error))
        form.addRow("Groq usage", self.groq_usage)
        form.addRow("Placeholder", self.placeholder_backend_status)
        form.addRow("Last backend", self.last_backend_used); form.addRow("Fallback used", self.fallback_used)
        form.addRow("Last user input", self.conversation_input); form.addRow("Last reply", self.conversation_reply)
        form.addRow("Conversation count", self.conversation_count); form.addRow("Processing time", self.conversation_time)
        form.addRow("Last AI error", self.ai_last_error)
        form.addRow("Personality", self.current_personality)
        form.addRow("Conversation Memory", self.memory_status)
        form.addRow("Recent messages", self.memory_recent_messages)
        form.addRow("Summary exists / size", self._button_row(self.memory_summary_exists, self.memory_summary_size))
        form.addRow("Summary updated", self.memory_summary_updated)
        form.addRow("Messages summarized", self.memory_messages_summarized)
        form.addRow("Estimated tokens", self.memory_estimated_tokens)
        form.addRow(self._button_row(self.view_memory_summary, self.force_memory_summary))
        form.addRow(self.clear_conversation_memory)
        form.addRow("Long-Term Memory", self.long_term_enabled)
        form.addRow("Storage available", self.long_term_storage)
        form.addRow("Total / enabled", self._button_row(self.long_term_total, self.long_term_enabled_count))
        form.addRow("Pending candidates", self.long_term_pending); form.addRow("Last saved", self.long_term_last_saved)
        form.addRow("Last retrieval count", self.long_term_retrieval_count)
        form.addRow("Retrieval latency", self.long_term_retrieval_latency)
        form.addRow(self._button_row(self.refresh_long_term, self.rebuild_memory_index))
        form.addRow(self._button_row(self.view_memory_storage_path, self.clear_pending_memories))
        self.view_memory_summary.clicked.connect(self._view_memory_summary)
        self.force_memory_summary.clicked.connect(manager.force_summary)
        self.clear_conversation_memory.clicked.connect(manager.clear_conversation_memory)
        self.refresh_long_term.clicked.connect(manager.refresh_long_term_memory_diagnostics)
        self.rebuild_memory_index.clicked.connect(manager.rebuild_long_term_memory_index)
        self.view_memory_storage_path.clicked.connect(self._view_memory_storage_path)
        self.clear_pending_memories.clicked.connect(manager.clear_pending_memory_candidates)
        return tab

    def _diagnostics_tab(self) -> QWidget:
        tab = QWidget(); layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8); layout.setSpacing(6)
        summary = QWidget(); form = self._form(summary)
        self.presence_state = self._readonly(self.voice_manager.state_manager.current_state.name)
        self.audio_mode = self._readonly(self.voice_manager.audio_controller.mode.name)
        self.backend_status = self._readonly(self.voice_manager.conversation_manager.backend_status)
        self.last_error = self._readonly()
        form.addRow("Presence", self.presence_state); form.addRow("Audio mode", self.audio_mode)
        form.addRow("Backend status", self.backend_status); form.addRow("Last error", self.last_error)
        layout.addWidget(summary)
        self.advanced_toggle = QToolButton(); self.advanced_toggle.setText("Advanced Details")
        self.advanced_toggle.setCheckable(True); self.advanced_toggle.setArrowType(Qt.RightArrow)
        layout.addWidget(self.advanced_toggle)
        self.advanced_details = QWidget(); advanced = self._form(self.advanced_details)
        self.threshold = self._readonly(f"{self.wake_manager.config.wake_confidence_threshold:.2f}")
        self.sample_rate = self._readonly(str(self.voice_manager.config.sample_rate))
        self.recording_duration = self._readonly("0.00 s")
        self.worker_status = self._readonly("idle")
        self.stt_status = self._readonly("idle"); self.tts_status = self._readonly("idle")
        self.microphone_ownership = self._readonly(self.voice_manager.audio_controller.mode.name)
        self.raw_details = self._readonly(f"STT: {self.voice_manager.stt_backend} · TTS: {self.voice_manager.tts_backend}")
        advanced.addRow("Wake threshold", self.threshold); advanced.addRow("Sample rate", self.sample_rate)
        advanced.addRow("Recording duration", self.recording_duration); advanced.addRow("Worker", self.worker_status)
        advanced.addRow("STT status", self.stt_status); advanced.addRow("TTS status", self.tts_status)
        advanced.addRow("Microphone owner", self.microphone_ownership); advanced.addRow("Technical", self.raw_details)
        self.advanced_details.hide(); layout.addWidget(self.advanced_details)
        self.event_log = QPlainTextEdit(); self.event_log.setReadOnly(True)
        self.event_log.setMaximumBlockCount(50); self.event_log.setFixedHeight(150)
        layout.addWidget(QLabel("Recent events")); layout.addWidget(self.event_log)
        self.advanced_toggle.toggled.connect(self._toggle_advanced)
        return tab

    def _connect_updates(self) -> None:
        self.wake_manager.backend_changed.connect(lambda text: self._set_field(self.backend, text))
        self.wake_manager.candidate_evaluated.connect(self._wake_candidate)
        self.wake_manager.status_changed.connect(self._wake_status_changed)
        self.wake_manager.monitoring_changed.connect(
            lambda active: self._wake_status_changed("monitoring" if active else "idle")
        )
        self.wake_manager.error.connect(self._error)
        self.voice_manager.error.connect(self._error)
        self.voice_manager.recognized_text.connect(self._recognized)
        self.voice_manager.reply_generated.connect(self._reply)
        self.voice_manager.listening_changed.connect(self._listening_changed)
        self.voice_manager.level_changed.connect(lambda value: self._set_field(self.input_level, f"{value:.5f}"))
        self.voice_manager.duration_changed.connect(lambda value: self._set_field(self.recording_duration, f"{value:.2f} s"))
        self.voice_manager.status_changed.connect(self._voice_status)
        self.voice_manager.synthesizer.started.connect(lambda: self._set_field(self.tts_status, "speaking"))
        self.voice_manager.synthesizer.finished.connect(lambda: self._set_field(self.tts_status, "idle"))
        self.voice_manager.state_manager.state_changed.connect(self._state_changed)
        self.voice_manager.conversation_manager.processing_started.connect(
            lambda text: self._set_field(self.worker_status, "processing")
        )
        self.voice_manager.conversation_manager.processing_finished.connect(
            lambda: self._set_field(self.worker_status, "idle")
        )
        self.voice_manager.conversation_manager.diagnostics_changed.connect(self._conversation_diagnostics)
        self.voice_manager.conversation_manager.openai_test_finished.connect(self._openai_test_result)
        self.voice_manager.conversation_manager.groq_test_finished.connect(self._groq_test_result)

    def _toggle_advanced(self, opened: bool) -> None:
        self.advanced_details.setVisible(opened)
        self.advanced_toggle.setArrowType(Qt.DownArrow if opened else Qt.RightArrow)

    def _wake_candidate(self, result, accepted, reason) -> None:
        self._set_field(self.confidence, f"{result.confidence:.2f}")
        self._log(f"Wake {'accepted' if accepted else 'rejected'}: {reason}")

    def _wake_status_changed(self, status: str) -> None:
        self._set_field(self.wake_status, status); self._log(f"Wake: {status}")

    def _voice_status(self, status: str) -> None:
        self._set_field(self.stt_status, status); self._log(f"Voice: {status}")

    def _recognized(self, text: str) -> None:
        self._set_field(self.recognized, text); self._log(f"Recognized: {text}")

    def _reply(self, text: str) -> None:
        self._set_field(self.reply, text); self._log(f"Reply: {text}")

    def _error(self, message: str) -> None:
        self._set_field(self.last_error, message); self._log(f"Error: {message}")

    def _state_changed(self, old, new) -> None:
        self._set_field(self.presence_state, new.name)
        mode = self.voice_manager.audio_controller.mode.name
        self._set_field(self.audio_mode, mode); self._set_field(self.microphone_ownership, mode)
        self._log(f"Presence: {new.name}")

    def _conversation_diagnostics(self, diagnostics: dict) -> None:
        self._set_field(self.conversation_backend, diagnostics["backend"])
        self._set_field(self.conversation_input, diagnostics["last_user_input"] or "—")
        self._set_field(self.conversation_reply, diagnostics["last_reply"] or "—")
        self._set_field(self.conversation_count, diagnostics["conversation_count"])
        self._set_field(self.conversation_time, f"{float(diagnostics['processing_seconds']):.3f} s")
        self._set_field(self.conversation_status, diagnostics["backend_status"])
        self._set_field(self.backend_status, diagnostics["backend_status"])
        self.hybrid_mode.blockSignals(True); self.hybrid_mode.setCurrentText(diagnostics["hybrid_mode"]); self.hybrid_mode.blockSignals(False)
        self._set_field(self.selected_backend, diagnostics["selected_backend"])
        statuses = diagnostics["backend_statuses"]
        self._set_field(self.local_backend_status, statuses.get("local", "unregistered"))
        self._set_field(self.openai_backend_status, statuses.get("openai", "unregistered"))
        self._set_field(self.groq_backend_status, statuses.get("groq", "unregistered"))
        self._set_field(self.placeholder_backend_status, statuses.get("placeholder", "unregistered"))
        self._set_field(self.last_backend_used, diagnostics["selected_backend"])
        self._set_field(self.fallback_used, "yes" if diagnostics["fallback_used"] else "no")
        self._set_field(self.ai_last_error, diagnostics["last_error"] or "—")
        self._set_field(self.current_personality, diagnostics["personality"])
        self._set_field(self.openai_model, diagnostics["openai_model"])
        self._set_field(self.openai_api_key, diagnostics["openai_api_key"])
        self._set_field(self.openai_environment_detected, diagnostics["openai_environment_detected"])
        self._set_field(self.openai_sdk_installed, diagnostics["openai_sdk_installed"])
        self._set_field(self.openai_backend_enabled, diagnostics["openai_backend_enabled"])
        self._set_field(self.cloud_ai_status, diagnostics["cloud_ai"])
        self.cloud_ai_allowed.blockSignals(True)
        self.cloud_ai_allowed.setChecked(diagnostics["cloud_ai"] == "allowed")
        self.cloud_ai_allowed.blockSignals(False)
        self._set_field(self.openai_response_id, diagnostics["openai_response_id"])
        self._set_field(self.openai_latency, f"{float(diagnostics['openai_latency']):.3f} s")
        usage = diagnostics["openai_usage"]
        self._set_field(self.openai_usage, (
            f"in={usage.get('input_tokens', '—')} out={usage.get('output_tokens', '—')} "
            f"total={usage.get('total_tokens', '—')}"
        ))
        self._set_field(self.openai_error_category, diagnostics["openai_error_category"])
        self._set_field(self.groq_model, diagnostics["groq_model"]); self._set_field(self.groq_api_key, diagnostics["groq_api_key"])
        self._set_field(self.groq_environment_detected, diagnostics["groq_environment_detected"])
        self._set_field(self.groq_sdk_installed, diagnostics["groq_sdk_installed"])
        self._set_field(self.groq_backend_enabled, diagnostics["groq_backend_enabled"])
        self._set_field(self.groq_response_id, diagnostics["groq_response_id"])
        self._set_field(self.groq_latency, f"{float(diagnostics['groq_latency']):.3f} s")
        groq_usage = diagnostics["groq_usage"]
        self._set_field(self.groq_usage, f"in={groq_usage.get('input_tokens', '—')} out={groq_usage.get('output_tokens', '—')} total={groq_usage.get('total_tokens', '—')}")
        self._set_field(self.groq_error, diagnostics["groq_error"])
        self._set_field(self.memory_recent_messages, diagnostics["memory_recent_messages"])
        self._set_field(self.memory_summary_exists, "yes" if diagnostics["memory_summary_exists"] else "no")
        self._set_field(self.memory_summary_size, diagnostics["memory_summary_size"])
        self._set_field(self.memory_summary_updated, diagnostics["memory_summary_updated"])
        self._set_field(self.memory_messages_summarized, diagnostics["memory_messages_summarized"])
        self._set_field(self.memory_estimated_tokens, diagnostics["memory_estimated_tokens"])
        self._set_field(self.memory_status, diagnostics["memory_status"])
        self._set_field(self.long_term_enabled, "yes" if diagnostics["long_term_enabled"] else "no")
        self._set_field(self.long_term_storage, "available" if diagnostics["long_term_storage_available"] else "unavailable")
        self._set_field(self.long_term_total, diagnostics["long_term_total"])
        self._set_field(self.long_term_enabled_count, diagnostics["long_term_enabled_count"])
        self._set_field(self.long_term_pending, diagnostics["long_term_pending"])
        self._set_field(self.long_term_last_saved, diagnostics["long_term_last_saved"])
        self._set_field(self.long_term_retrieval_count, diagnostics["long_term_last_retrieval_count"])
        self._set_field(self.long_term_retrieval_latency, f"{float(diagnostics['long_term_last_retrieval_latency']):.3f} s")

    def _view_memory_summary(self) -> None:
        summary = self.voice_manager.conversation_manager.memory.summary
        QMessageBox.information(self, "Conversation Summary",
                                summary.text if summary else "No conversation summary exists yet.")

    def _view_memory_storage_path(self) -> None:
        path = self.voice_manager.conversation_manager.long_term_memory.path
        QMessageBox.information(self, "Long-Term Memory Storage", path)

    def _test_openai(self) -> None:
        self.test_openai.setEnabled(False)
        if not self.voice_manager.conversation_manager.test_openai_connection():
            self.test_openai.setEnabled(True)

    def _openai_test_result(self, result: dict) -> None:
        self.test_openai.setEnabled(True)
        if result.get("success"):
            message = (f"SUCCESS\nBackend: {result['backend']}\nModel: {result['model']}\n"
                       f"Response time: {result['elapsed']:.3f} s\nResponse: {result['text']}")
        else:
            message = f"FAILURE\nCategory: {result.get('category', 'unknown')}\n{result.get('message', '')}"
        self.test_openai.setToolTip(message); self._log(message.replace("\n", " · "))

    def _test_groq(self) -> None:
        self.test_groq.setEnabled(False)
        if not self.voice_manager.conversation_manager.test_groq_connection():
            self.test_groq.setEnabled(True)

    def _groq_test_result(self, result: dict) -> None:
        self.test_groq.setEnabled(True)
        if result.get("success"):
            message = (f"SUCCESS\nBackend: {result['backend']}\nModel: {result['model']}\n"
                       f"Response time: {result['elapsed']:.3f} s\nResponse: {result['text']}\n"
                       f"Usage: {result.get('usage', {})}")
        else:
            message = (f"FAILURE\nCategory: {result.get('category', 'unknown')}\n"
                       f"Code: {result.get('code', '—')}\n{result.get('message', '')}")
        self.test_groq.setToolTip(message); self._log(message.replace("\n", " · "))

    def _preview_personality_prompt(self) -> None:
        prompt = self.voice_manager.conversation_manager.preview_system_prompt()
        self.preview_personality_prompt.setToolTip(prompt)
        message = QMessageBox(self)
        message.setWindowTitle("ADRIEN System Prompt")
        message.setText("Current provider-independent personality prompt")
        message.setDetailedText(prompt)
        message.exec()

    def _listening_changed(self, active: bool) -> None:
        self.voice_stop.setEnabled(active); self.voice_cancel.setEnabled(active)
        self._set_field(self.stt_status, "listening" if active else "idle")

    def _submit_text(self) -> None:
        text = self.test_input.text().strip()
        if text and self.voice_manager.submit_debug_text(text): self.test_input.clear()

    def _log(self, message: str) -> None:
        self.event_log.appendPlainText(f"{datetime.now():%H:%M:%S}  {message}")

    def set_test_buttons_visible(self, visible: bool) -> None:
        for control in (self.voice_start, self.voice_stop, self.voice_cancel, self.test_input,
                        self.wake_start, self.wake_stop, self.simulate_wake, self.force_sleep,
                        self.simulate_low, self.simulate_high):
            control.setVisible(visible)
