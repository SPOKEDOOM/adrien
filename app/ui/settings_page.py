from __future__ import annotations

import platform

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QListWidget,
    QMessageBox, QPushButton, QScrollArea, QSlider, QStackedWidget, QVBoxLayout, QWidget,
)
from app.ui.ai_providers_page import AIProvidersPage


class ProviderCard(QFrame):
    make_default = Signal(str); test_requested = Signal(str)

    def __init__(self, provider, title, configurable=True, parent=None):
        super().__init__(parent); self.provider = provider; self.setObjectName("providerCard")
        layout = QVBoxLayout(self); heading = QLabel(title); heading.setObjectName("cardTitle"); layout.addWidget(heading)
        form = QFormLayout(); self.status = QLabel("Unavailable"); self.model = QLabel("—")
        self.configured = QLabel("No"); self.sdk = QLabel("—"); self.latency = QLabel("0.000 s")
        self.usage = QLabel("—"); self.error = QLabel("—")
        for label, widget in (("Status", self.status), ("Model", self.model), ("Configured key", self.configured),
                              ("SDK installed", self.sdk), ("Last latency", self.latency),
                              ("Last usage", self.usage), ("Last error", self.error)): form.addRow(label, widget)
        layout.addLayout(form); buttons = QHBoxLayout(); self.test = QPushButton("Test Connection")
        self.configure = QPushButton("Configure"); self.default = QPushButton("Make Default")
        if provider == "placeholder": self.test.hide(); self.configure.hide()
        if provider == "local": self.test.setText("Install")
        buttons.addWidget(self.test); buttons.addWidget(self.configure); buttons.addWidget(self.default); layout.addLayout(buttons)
        self.test.clicked.connect(lambda: self.test_requested.emit(provider))
        self.default.clicked.connect(lambda: self.make_default.emit(provider))
        self.configure.clicked.connect(self._show_configuration)

    def _show_configuration(self):
        QMessageBox.information(self, f"Configure {self.provider.title()}",
                                "Provider secrets are configured through environment variables. No API key is displayed or stored here.")


class SettingsPage(QWidget):
    developer_mode_changed = Signal(bool)
    open_developer_tools_requested = Signal()

    def __init__(self, settings, conversation_manager, parent=None):
        super().__init__(parent); self.settings = settings; self.manager = conversation_manager
        self.page_widgets = {
            "Voice": self._voice(), "Memory": self._memory(), "AI Providers": self._providers(),
            "Privacy": self._privacy(), "Developer": self._developer(), "About": self._about(),
        }
        self.manager.diagnostics_changed.connect(self.update_diagnostics)
        self.update_diagnostics(self.manager.diagnostics_snapshot())
        style = """
            QWidget { background:#10151d; color:#dce8f5; }
            QListWidget { background:#151c26; border:1px solid #263648; border-radius:10px; padding:8px; }
            QListWidget::item { padding:10px; border-radius:6px; } QListWidget::item:selected { background:#24445f; }
            QFrame#providerCard { background:#151d27; border:1px solid #2a3d50; border-radius:12px; padding:10px; }
            QLabel#cardTitle { font-size:18px; font-weight:600; color:#8ed8ff; }
            QPushButton, QComboBox { min-height:28px; } QCheckBox { spacing:8px; }
        """
        self.setStyleSheet(style)
        for page in self.page_widgets.values(): page.setStyleSheet(style)

    @staticmethod
    def _page(title):
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget(); layout = QVBoxLayout(content); heading = QLabel(title); heading.setObjectName("cardTitle")
        layout.addWidget(heading); scroll.setWidget(content); return scroll, layout

    def _general(self):
        page, layout = self._page("General"); form = QFormLayout(); form.addRow("Application", QLabel("ADRIEN"))
        startup = QComboBox(); startup.addItems(["Start normally", "Start minimized"])
        form.addRow("Startup behaviour", startup)
        form.addRow("Auto update", QLabel("Planned")); form.addRow("Language", QLabel("English (future setting)"))
        form.addRow("Theme shortcut", QLabel("System default")); layout.addLayout(form); layout.addStretch(); return page

    def _appearance(self):
        page, layout = self._page("Appearance"); layout.addWidget(QLabel("ADRIEN dark theme · additional appearance settings are planned.")); layout.addStretch(); return page

    def _voice(self):
        page, layout = self._page("Voice"); form = QFormLayout(); voice = QComboBox(); voice.addItem("System voice")
        rate = QSlider(Qt.Horizontal); rate.setValue(50); volume = QSlider(Qt.Horizontal); volume.setValue(80)
        wake = QComboBox(); wake.addItem("Adrien")
        for label, widget in (("Voice", voice), ("Speech rate", rate), ("Speech volume", volume), ("Wake word", wake)): form.addRow(label, widget)
        layout.addLayout(form); layout.addWidget(QLabel("These controls prepare future voice configuration.")); layout.addStretch(); return page

    def _providers(self):
        page = AIProvidersPage(self.settings, self.manager)
        self.ai_providers_page = page; self.provider_cards = page.provider_cards
        self.default_provider = page.default_provider; self.routing_priority = page.routing_priority
        self.refresh_providers = page.refresh_button
        self.priority = QListWidget(); self.priority.addItems([p.title() for p in self.settings.provider_priority])
        return page

    def _privacy(self):
        page, layout = self._page("Privacy"); self.cloud_processing = QCheckBox("Allow Cloud Processing")
        self.cloud_processing.setChecked(self.settings.cloud_processing); self.cloud_processing.toggled.connect(lambda value: self.settings.set_value("privacy/cloud_processing", value))
        layout.addWidget(self.cloud_processing); layout.addWidget(QLabel("When disabled, neither Groq nor OpenAI receives conversation text.")); layout.addStretch(); return page

    def _memory(self):
        page, layout = self._page("Memory");
        for text in ("Memory Enabled", "Conversation Memory", "Long-term Memory"):
            control = QCheckBox(text); control.setEnabled(False); layout.addWidget(control)
        clear = QPushButton("Clear Memory"); clear.setEnabled(False); layout.addWidget(clear); layout.addWidget(QLabel("Coming soon — these controls are previews only; no long-term storage is active.")); layout.addStretch(); return page

    def _developer(self):
        page, layout = self._page("Developer"); self.developer_mode = QCheckBox("Enable Developer Mode")
        self.diagnostics = QCheckBox("Enable Diagnostics"); self.debug_logging = QCheckBox("Enable Debug Logging")
        self.experimental = QCheckBox("Enable Experimental Features"); self.test_buttons = QCheckBox("Enable Test Controls")
        controls = ((self.developer_mode, "developer/mode", self.settings.developer_mode),
                    (self.diagnostics, "developer/diagnostics", self.settings.diagnostics_enabled),
                    (self.debug_logging, "developer/debug_logging", self.settings.debug_logging),
                    (self.experimental, "developer/experimental", self.settings.experimental_features),
                    (self.test_buttons, "developer/test_buttons", self.settings.test_buttons))
        for control, key, value in controls:
            control.setChecked(value); control.toggled.connect(lambda checked, name=key: self.settings.set_value(name, checked)); layout.addWidget(control)
        self.open_developer_tools = QPushButton("Open Developer Tools")
        self.open_developer_tools.clicked.connect(self.open_developer_tools_requested)
        layout.addWidget(self.open_developer_tools)
        self.developer_mode.toggled.connect(self.developer_mode_changed); layout.addStretch(); return page

    def page(self, name: str) -> QWidget:
        return self.page_widgets[name]

    def _about(self):
        page, layout = self._page("About"); form = QFormLayout(); self.detected_providers = QLabel()
        for label, value in (("Application", "ADRIEN"), ("Version", "0.7.5"), ("Python", platform.python_version()),
                             ("Qt/PySide", PYSIDE_VERSION), ("AI providers detected", self.detected_providers), ("License", "Development build")): form.addRow(label, value if isinstance(value, QWidget) else QLabel(value))
        layout.addLayout(form); layout.addStretch(); return page

    def _set_default(self, provider):
        self.ai_providers_page.select_provider(provider)

    def _make_default(self, provider): self.default_provider.setCurrentText(provider.title())
    def _move_priority(self, direction):
        row = self.priority.currentRow(); target = row + direction
        if row < 0 or target < 0 or target >= self.priority.count(): return
        item = self.priority.takeItem(row); self.priority.insertItem(target, item); self.priority.setCurrentRow(target)
        order = [self.priority.item(i).text().lower() for i in range(self.priority.count())]
        self.settings.set_provider_priority(order); self.manager.ai_manager.config.provider_priority = tuple(order); self.manager._emit_diagnostics()
    def _test_provider(self, provider):
        if provider == "groq": self.manager.test_groq_connection()
        elif provider == "openai": self.manager.test_openai_connection()
        elif provider == "local": QMessageBox.information(self, "Local AI", "Local AI installation is not implemented yet.")

    def update_diagnostics(self, data):
        self.ai_providers_page.update_diagnostics(data)
        self.detected_providers.setText(", ".join(name.title() for name in data["backend_statuses"]))
