from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


class ProviderCard(QFrame):
    selected = Signal(str)
    test_requested = Signal(str)

    def __init__(self, provider: str, title: str, parent=None):
        super().__init__(parent); self.provider = provider; self.setObjectName("providerCard")
        self.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(self); heading = QLabel(title); heading.setObjectName("cardTitle")
        layout.addWidget(heading); form = QFormLayout()
        self.fields = {}
        for key, label, initial in (
            ("status", "Status", "Unavailable"), ("configured", "API key configured", "No"),
            ("source", "Key source", "Unavailable"), ("preview", "Key preview", "—"),
            ("sdk", "SDK installed", "—"), ("enabled", "Backend enabled", "—"),
            ("availability", "Availability", "Unavailable"), ("model", "Model", "—"),
            ("test", "Last test result", "Not tested"), ("latency", "Last latency", "0.000 s"),
            ("error", "Last error", "—"),
        ):
            value = QLabel(initial); value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.fields[key] = value; setattr(self, key, value); form.addRow(label, value)
        heading.setAttribute(Qt.WA_TransparentForMouseEvents, True); layout.addLayout(form)
        row = QHBoxLayout(); self.test_button = QPushButton("Test Connection")
        self.select_button = QPushButton("Select")
        if provider == "placeholder": self.test_button.hide()
        row.addWidget(self.test_button); row.addWidget(self.select_button); layout.addLayout(row)
        self.test_button.clicked.connect(lambda: self.test_requested.emit(provider))
        self.select_button.clicked.connect(lambda: self.selected.emit(provider))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self.selected.emit(self.provider)
        super().mousePressEvent(event)

    def set_active(self, active: bool):
        self.setProperty("active", active); self.style().unpolish(self); self.style().polish(self)
        self.select_button.setText("Selected" if active else "Select")


class AIProvidersPage(QScrollArea):
    """Provider controls wired to the live ConversationManager and settings store."""

    def __init__(self, settings, manager, parent=None):
        super().__init__(parent); self.settings = settings; self.manager = manager
        self.setWidgetResizable(True); self.setFrameShape(QFrame.NoFrame)
        content = QWidget(); layout = QVBoxLayout(content); self.setWidget(content)
        heading = QLabel("AI Providers"); heading.setObjectName("cardTitle"); layout.addWidget(heading)
        selector = QHBoxLayout(); self.provider_group = QButtonGroup(self); self.provider_group.setExclusive(True)
        self.provider_buttons = {}
        for value, title in (("automatic", "Automatic"), ("groq", "Groq"),
                             ("openai", "OpenAI"), ("placeholder", "Offline")):
            button = QPushButton(title); button.setCheckable(True)
            button.clicked.connect(lambda checked=False, name=value: self.select_provider(name))
            self.provider_group.addButton(button); self.provider_buttons[value] = button; selector.addWidget(button)
        layout.addLayout(selector)
        form = QFormLayout(); self.default_provider = QComboBox()
        self.default_provider.addItems(["Automatic", "Groq", "OpenAI", "Placeholder"])
        self.default_provider.currentTextChanged.connect(lambda value: self.select_provider(value.lower()))
        self.routing_priority = QComboBox()
        for title, value in (("Groq first", "groq_first"), ("OpenAI first", "openai_first"),
                             ("Best available", "automatic")): self.routing_priority.addItem(title, value)
        self.routing_priority.setCurrentIndex(max(0, self.routing_priority.findData(settings.routing_mode)))
        self.routing_priority.currentIndexChanged.connect(self._routing_changed)
        form.addRow("Default provider", self.default_provider); form.addRow("Routing priority", self.routing_priority)
        layout.addLayout(form); self.automatic_status = QLabel(); layout.addWidget(self.automatic_status)
        self.provider_cards = {}
        for name, title in (("groq", "Groq"), ("openai", "OpenAI"),
                            ("placeholder", "Placeholder / Offline")):
            card = ProviderCard(name, title); card.selected.connect(self.select_provider)
            card.test_requested.connect(self.test_provider); self.provider_cards[name] = card; layout.addWidget(card)
        self.refresh_button = QPushButton("Refresh Status"); self.confirmation = QLabel()
        note = QLabel("Refresh rereads this process and .env. Variables added in another terminal may require relaunching ADRIEN.")
        note.setWordWrap(True); layout.addWidget(self.refresh_button); layout.addWidget(self.confirmation); layout.addWidget(note)
        self.refresh_button.clicked.connect(self.refresh_status)
        manager.groq_test_finished.connect(lambda result: self._test_result("groq", result))
        manager.openai_test_finished.connect(lambda result: self._test_result("openai", result))
        manager.diagnostics_changed.connect(self.update_diagnostics)
        self.setStyleSheet("""
            QWidget { background:#10151d; color:#dce8f5; }
            QFrame#providerCard { background:#151d27; border:1px solid #2a3d50; border-radius:12px; padding:10px; }
            QFrame#providerCard[active="true"] { background:#192b3a; border:2px solid #70d7ff; }
            QLabel#cardTitle { font-size:18px; font-weight:600; color:#8ed8ff; }
            QPushButton, QComboBox { min-height:28px; }
            QPushButton:checked { background:#244f69; border:1px solid #70d7ff; }
        """)
        self._sync_selection(); self.update_diagnostics(manager.diagnostics_snapshot())

    def select_provider(self, provider: str):
        if provider not in self.provider_buttons: return
        self.settings.set_default_provider(provider)
        config = self.manager.ai_manager.config
        config.default_backend = "auto" if provider == "automatic" else provider
        mode = self.settings.routing_mode if provider == "automatic" else {
            "groq": "groq_only", "openai": "openai_only", "placeholder": "placeholder_only"}[provider]
        self.manager.set_hybrid_mode(mode); self._sync_selection(); self.confirmation.setText("Provider preference saved")

    def _routing_changed(self):
        mode = self.routing_priority.currentData()
        if not mode: return
        self.settings.set_routing_mode(mode)
        if self.settings.default_provider == "automatic": self.manager.set_hybrid_mode(mode)
        self.confirmation.setText("Routing priority saved")

    def _sync_selection(self):
        selected = self.settings.default_provider
        if selected not in self.provider_buttons: selected = "automatic"
        self.provider_buttons[selected].setChecked(True)
        self.default_provider.blockSignals(True); self.default_provider.setCurrentText(selected.title())
        self.default_provider.blockSignals(False); self.routing_priority.setEnabled(selected == "automatic")
        for name, card in self.provider_cards.items(): card.set_active(name == selected)

    def refresh_status(self):
        self.refresh_button.setEnabled(False); self.refresh_button.setText("Refreshing…")
        try:
            self.manager.refresh_provider_configuration()
            self.update_diagnostics(self.manager.diagnostics_snapshot()); self.confirmation.setText("Provider status refreshed")
        finally:
            self.refresh_button.setText("Refresh Status"); self.refresh_button.setEnabled(True)

    def test_provider(self, provider: str):
        card = self.provider_cards[provider]; card.test_button.setEnabled(False); card.test_button.setText("Testing…")
        if provider == "groq": self.manager.test_groq_connection()
        elif provider == "openai": self.manager.test_openai_connection()

    def _test_result(self, provider: str, result: dict):
        card = self.provider_cards[provider]; card.test_button.setEnabled(True); card.test_button.setText("Test Connection")
        if result.get("success"):
            card.test.setText("Success"); card.error.setText("—")
            card.latency.setText(f"{float(result.get('elapsed', 0)):.3f} s")
        else:
            category = result.get("category", "unknown"); card.test.setText(f"Failed: {category}")
            card.error.setText(result.get("message", "Provider test failed"))

    def update_diagnostics(self, data: dict):
        statuses = data["backend_statuses"]
        for provider in ("groq", "openai"):
            card = self.provider_cards[provider]
            card.status.setText(statuses.get(provider, "unavailable").title())
            card.availability.setText(statuses.get(provider, "unavailable").title())
            card.configured.setText("Yes" if data[f"{provider}_api_key"] == "configured" else "No")
            card.source.setText(data[f"{provider}_key_source"]); card.preview.setText(data[f"{provider}_key_preview"])
            card.sdk.setText(data[f"{provider}_sdk_installed"].title())
            card.enabled.setText(data[f"{provider}_backend_enabled"].title()); card.model.setText(data[f"{provider}_model"])
            card.latency.setText(f"{float(data[f'{provider}_latency']):.3f} s")
        offline = self.provider_cards["placeholder"]; offline.status.setText("Available")
        offline.availability.setText("Available"); offline.configured.setText("Not required")
        offline.source.setText("Offline"); offline.preview.setText("—"); offline.sdk.setText("Built in")
        offline.enabled.setText("Yes"); offline.model.setText("Built in")
        self.automatic_status.setText(
            f"Automatic: {self.settings.routing_mode.replace('_', ' ').title()} · "
            f"Last backend: {data['selected_backend']} · Fallback: {'Yes' if data['fallback_used'] else 'No'}")
        self._sync_selection()
