from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QScrollArea

from app.ui.main_window import MainWindow


class DeveloperToolsLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow(); self.window.show(); self.app.processEvents()

    def tearDown(self):
        self.window.close(); self.app.processEvents()

    def test_hidden_by_default_opens_closes_and_has_four_tabs(self):
        panel = self.window.developer_tools_panel
        self.assertFalse(self.window.developer_dock.isVisible())
        self.assertNotIsInstance(panel, QScrollArea)
        self.assertEqual([panel.tabs.tabText(i) for i in range(panel.tabs.count())],
                         ["Voice", "Wake", "Conversation", "Diagnostics"])
        self.window.toggle_developer_tools(); self.assertTrue(self.window.developer_dock.isVisible())
        self.window.toggle_developer_tools(); self.assertFalse(self.window.developer_dock.isVisible())

    def test_each_tab_exposes_required_controls(self):
        panel = self.window.developer_tools_panel
        for index, controls in enumerate((
            (panel.voice_start, panel.voice_stop, panel.voice_cancel, panel.microphone, panel.recognized, panel.reply),
            (panel.wake_start, panel.wake_stop, panel.simulate_wake, panel.force_sleep, panel.backend, panel.confidence),
            (panel.conversation_backend, panel.conversation_input, panel.conversation_reply,
             panel.conversation_count, panel.conversation_time, panel.clear_conversation,
             panel.hybrid_mode, panel.local_backend_status, panel.openai_backend_status,
             panel.placeholder_backend_status, panel.run_hybrid_test, panel.cancel_ai_request,
             panel.current_personality, panel.reload_personality, panel.preview_personality_prompt),
            (panel.presence_state, panel.audio_mode, panel.stt_status, panel.tts_status,
             panel.last_error, panel.event_log),
        )):
            panel.tabs.setCurrentIndex(index); self.app.processEvents()
            self.assertTrue(all(control is not None for control in controls))

    def test_log_scrolls_internally_is_bounded_and_advanced_starts_closed(self):
        panel = self.window.developer_tools_panel
        self.assertIsInstance(panel.event_log, QPlainTextEdit)
        self.assertTrue(panel.advanced_details.isHidden())
        panel.advanced_toggle.click(); self.assertFalse(panel.advanced_details.isHidden())
        for index in range(70): panel._log(f"event {index}")
        self.assertLessEqual(panel.event_log.document().blockCount(), 50)
        self.assertIsNotNone(panel.event_log.verticalScrollBar())

    def test_switching_tabs_and_floating_panel_do_not_resize_main_or_move_core(self):
        original_size = self.window.size(); original_geometry = self.window.core.geometry()
        self.window.toggle_developer_tools(); self.app.processEvents()
        for index in range(4):
            self.window.developer_tools_panel.tabs.setCurrentIndex(index); self.app.processEvents()
            self.assertEqual(self.window.size(), original_size)
            self.assertEqual(self.window.core.geometry(), original_geometry)

    def test_tab_shortcuts_only_enabled_while_tools_visible(self):
        self.assertTrue(all(not shortcut.isEnabled() for shortcut in self.window._developer_tab_shortcuts))
        self.window.toggle_developer_tools(); self.app.processEvents()
        self.assertTrue(all(shortcut.isEnabled() for shortcut in self.window._developer_tab_shortcuts))
        QTest.keyClick(self.window, Qt.Key_3, Qt.ControlModifier)
        self.assertEqual(self.window.developer_tools_panel.tabs.currentIndex(), 2)
        self.window.toggle_developer_tools(); self.app.processEvents()
        self.assertTrue(all(not shortcut.isEnabled() for shortcut in self.window._developer_tab_shortcuts))


if __name__ == "__main__": unittest.main()
