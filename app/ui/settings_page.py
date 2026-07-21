from __future__ import annotations

import platform

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QInputDialog, QLineEdit, QMessageBox, QPushButton, QScrollArea, QSlider, QSpinBox,
    QStackedWidget, QVBoxLayout, QWidget,
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
        page, layout = self._page("Memory"); form = QFormLayout()
        self.memory_summaries = QCheckBox("Enable conversation summaries")
        self.memory_summaries.setChecked(self.settings.memory_summaries_enabled)
        self.memory_recent = QSpinBox(); self.memory_recent.setRange(2, 200)
        self.memory_recent.setValue(self.settings.memory_maximum_recent_messages)
        self.memory_threshold = QSpinBox(); self.memory_threshold.setRange(2, 400)
        self.memory_threshold.setValue(self.settings.memory_summary_threshold)
        self.memory_summary_words = QSpinBox(); self.memory_summary_words.setRange(20, 500)
        self.memory_summary_words.setValue(self.settings.memory_maximum_summary_words)
        form.addRow(self.memory_summaries); form.addRow("Maximum recent messages", self.memory_recent)
        form.addRow("Summary threshold", self.memory_threshold)
        form.addRow("Maximum summary words", self.memory_summary_words); layout.addLayout(form)
        self.clear_memory = QPushButton("Clear Conversation Memory"); layout.addWidget(self.clear_memory)
        layout.addWidget(QLabel("Conversation memory is session-only and remains separate from saved memory."))
        self.memory_summaries.toggled.connect(lambda value: self._memory_changed("memory/conversation_summaries_enabled", value))
        self.memory_recent.valueChanged.connect(lambda value: self._memory_changed("memory/maximum_recent_messages", value))
        self.memory_threshold.valueChanged.connect(lambda value: self._memory_changed("memory/summary_threshold", value))
        self.memory_summary_words.valueChanged.connect(lambda value: self._memory_changed("memory/maximum_summary_words", value))
        self.clear_memory.clicked.connect(self.manager.clear_conversation_memory)

        heading = QLabel("Long-Term Memory"); heading.setObjectName("cardTitle"); layout.addWidget(heading)
        self.long_term_enabled = QCheckBox("Enable Long-Term Memory"); self.long_term_enabled.setChecked(self.settings.long_term_memory_enabled)
        self.memory_suggestions = QCheckBox("Allow Memory Suggestions"); self.memory_suggestions.setChecked(self.settings.memory_suggestions_enabled)
        self.memory_ask = QCheckBox("Ask Before Saving"); self.memory_ask.setChecked(self.settings.memory_ask_before_saving)
        self.maximum_memories = QSpinBox(); self.maximum_memories.setRange(1, 5000); self.maximum_memories.setValue(self.settings.maximum_long_term_memories)
        lt_form = QFormLayout(); lt_form.addRow(self.long_term_enabled); lt_form.addRow(self.memory_suggestions)
        lt_form.addRow(self.memory_ask); lt_form.addRow("Maximum memories", self.maximum_memories); layout.addLayout(lt_form)
        self.long_term_status = QLabel(); layout.addWidget(self.long_term_status)
        filters = QHBoxLayout(); self.memory_search = QLineEdit(); self.memory_search.setPlaceholderText("Search memories")
        self.memory_category = QComboBox(); self.memory_category.addItem("All categories", "")
        for category in ("identity", "preference", "project", "goal", "routine", "tool", "note"):
            self.memory_category.addItem(category.title(), category)
        self.memory_sort = QComboBox()
        for title, value in (("Recent", "recent"), ("Oldest", "oldest"), ("Importance", "importance"), ("Last used", "last_used")):
            self.memory_sort.addItem(title, value)
        filters.addWidget(self.memory_search, 1); filters.addWidget(self.memory_category); filters.addWidget(self.memory_sort); layout.addLayout(filters)
        self.long_term_list = QListWidget(); layout.addWidget(self.long_term_list)
        actions = QHBoxLayout(); self.add_long_term = QPushButton("Add") ; self.view_long_term = QPushButton("View")
        self.edit_long_term = QPushButton("Edit"); self.delete_long_term = QPushButton("Delete")
        self.toggle_long_term = QPushButton("Disable / Enable"); self.pin_long_term = QPushButton("Pin")
        for button in (self.add_long_term, self.view_long_term, self.edit_long_term,
                       self.delete_long_term, self.toggle_long_term, self.pin_long_term): actions.addWidget(button)
        layout.addLayout(actions); self.clear_long_term = QPushButton("Clear All Long-Term Memory"); layout.addWidget(self.clear_long_term)
        self.candidate_panel = QFrame(); candidate_layout = QHBoxLayout(self.candidate_panel)
        self.candidate_text = QLabel("No pending memory suggestions"); self.candidate_text.setWordWrap(True)
        self.remember_candidate = QPushButton("Remember"); self.dismiss_candidate = QPushButton("Dismiss")
        self.never_candidate = QPushButton("Never Suggest This Category")
        candidate_layout.addWidget(self.candidate_text, 1); candidate_layout.addWidget(self.remember_candidate)
        candidate_layout.addWidget(self.dismiss_candidate); candidate_layout.addWidget(self.never_candidate); layout.addWidget(self.candidate_panel)
        for control, key in ((self.long_term_enabled, "memory/long_term_enabled"),
                             (self.memory_suggestions, "memory/suggestions_enabled"),
                             (self.memory_ask, "memory/ask_before_saving")):
            control.toggled.connect(lambda value, setting=key: self._long_term_setting_changed(setting, value))
        self.maximum_memories.valueChanged.connect(lambda value: self._long_term_setting_changed("memory/maximum_memories", value))
        self.memory_search.textChanged.connect(self._refresh_long_term_memories)
        self.memory_category.currentIndexChanged.connect(self._refresh_long_term_memories)
        self.memory_sort.currentIndexChanged.connect(self._refresh_long_term_memories)
        self.add_long_term.clicked.connect(self._add_long_term_memory); self.view_long_term.clicked.connect(self._view_long_term_memory)
        self.edit_long_term.clicked.connect(self._edit_long_term_memory); self.delete_long_term.clicked.connect(self._delete_long_term_memory)
        self.toggle_long_term.clicked.connect(self._toggle_long_term_memory); self.pin_long_term.clicked.connect(self._pin_long_term_memory)
        self.clear_long_term.clicked.connect(self._clear_long_term_memories)
        self.remember_candidate.clicked.connect(lambda: self._candidate_action("approve"))
        self.dismiss_candidate.clicked.connect(lambda: self._candidate_action("dismiss"))
        self.never_candidate.clicked.connect(lambda: self._candidate_action("never"))
        self.manager.diagnostics_changed.connect(lambda data: self._refresh_long_term_memories())
        self._refresh_long_term_memories()
        layout.addStretch(); return page

    def _memory_changed(self, key, value):
        self.settings.set_value(key, value)
        self.manager.configure_memory(self.memory_recent.value(), self.memory_threshold.value(),
                                      self.memory_summary_words.value(), self.memory_summaries.isChecked())

    def _long_term_setting_changed(self, key, value):
        self.settings.set_value(key, value)
        self.manager.configure_long_term_memory(self.long_term_enabled.isChecked(), self.memory_suggestions.isChecked(),
                                                self.memory_ask.isChecked(), self.maximum_memories.value(),
                                                self.settings.disabled_memory_suggestion_categories)

    def _refresh_long_term_memories(self):
        if not hasattr(self, "long_term_list"): return
        memory = self.manager.long_term_memory; selected = self._selected_long_term_id()
        items = memory.list(category=self.memory_category.currentData() or None,
                            search=self.memory_search.text(), sort=self.memory_sort.currentData())
        self.long_term_list.clear()
        for entry in items:
            state = "enabled" if entry.enabled else "disabled"
            item = QListWidgetItem(
                f"{entry.title}  [{entry.category}]  · {state}\n{entry.content[:120]}\nCreated: {entry.created_at[:10]}  Last used: {(entry.last_used_at or '—')[:19]}")
            item.setData(Qt.UserRole, entry.id); self.long_term_list.addItem(item)
            if entry.id == selected: self.long_term_list.setCurrentItem(item)
        diagnostics = memory.diagnostics()
        self.long_term_status.setText(f"Enabled: {'Yes' if diagnostics['enabled'] else 'No'} · Total: {diagnostics['total']} · Storage: {'Available' if diagnostics['storage_available'] else 'Unavailable'} · Last saved: {diagnostics['last_saved']}")
        candidates = tuple(memory.pending_candidates.values()); self._current_candidate = candidates[0] if candidates else None
        self.candidate_text.setText((f"Suggested [{self._current_candidate.category}]: {self._current_candidate.content}"
                                     if self._current_candidate else "No pending memory suggestions"))
        for button in (self.remember_candidate, self.dismiss_candidate, self.never_candidate): button.setEnabled(bool(self._current_candidate))

    def _selected_long_term_id(self):
        item = self.long_term_list.currentItem() if hasattr(self, "long_term_list") else None
        return item.data(Qt.UserRole) if item else None

    def _add_long_term_memory(self):
        title, ok = QInputDialog.getText(self, "Add Memory", "Title")
        if not ok or not title.strip(): return
        content, ok = QInputDialog.getMultiLineText(self, "Add Memory", "Content")
        if not ok or not content.strip(): return
        category, ok = QInputDialog.getItem(self, "Add Memory", "Category", ["identity", "preference", "project", "goal", "routine", "tool", "note"], editable=False)
        if not ok: return
        try: self.manager.long_term_memory.create(category, title, content, source="manual")
        except ValueError as exc: QMessageBox.warning(self, "Memory Not Saved", str(exc))
        self._refresh_long_term_memories()

    def _view_long_term_memory(self):
        memory = self.manager.long_term_memory.get(self._selected_long_term_id())
        if memory: QMessageBox.information(self, memory.title, f"Category: {memory.category}\nImportance: {memory.importance}\n\n{memory.content}")

    def _edit_long_term_memory(self):
        memory = self.manager.long_term_memory.get(self._selected_long_term_id())
        if not memory: return
        title, ok = QInputDialog.getText(self, "Edit Memory", "Title", text=memory.title)
        if not ok: return
        content, ok = QInputDialog.getMultiLineText(self, "Edit Memory", "Content", text=memory.content)
        if not ok: return
        try: self.manager.long_term_memory.update(memory.id, title=title, content=content)
        except ValueError as exc: QMessageBox.warning(self, "Memory Not Saved", str(exc))
        self._refresh_long_term_memories()

    def _delete_long_term_memory(self):
        identifier = self._selected_long_term_id()
        if identifier and QMessageBox.question(self, "Delete Memory", "Delete the selected long-term memory?") == QMessageBox.Yes:
            self.manager.long_term_memory.delete(identifier); self._refresh_long_term_memories()

    def _toggle_long_term_memory(self):
        memory = self.manager.long_term_memory.get(self._selected_long_term_id())
        if memory: self.manager.long_term_memory.update(memory.id, enabled=not memory.enabled); self._refresh_long_term_memories()

    def _pin_long_term_memory(self):
        memory = self.manager.long_term_memory.get(self._selected_long_term_id())
        if memory: self.manager.long_term_memory.update(memory.id, importance=min(5, memory.importance + 1)); self._refresh_long_term_memories()

    def _clear_long_term_memories(self):
        if QMessageBox.question(self, "Clear Long-Term Memory", "Permanently delete all saved long-term memories?") == QMessageBox.Yes:
            self.manager.long_term_memory.clear(); self._refresh_long_term_memories()

    def _candidate_action(self, action):
        candidate = getattr(self, "_current_candidate", None)
        if not candidate: return
        if action == "approve": self.manager.long_term_memory.approve_candidate(candidate.id)
        elif action == "dismiss": self.manager.long_term_memory.dismiss_candidate(candidate.id)
        else:
            self.manager.long_term_memory.disable_candidate_category(candidate.id)
            self.settings.set_value("memory/disabled_suggestion_categories",
                                    list(self.manager.long_term_memory.disabled_categories))
        self._refresh_long_term_memories()

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
