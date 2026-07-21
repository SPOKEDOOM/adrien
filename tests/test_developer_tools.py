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
        self.assertFalse(panel.isVisible())
        self.assertNotIsInstance(panel, QScrollArea)
        self.assertEqual([panel.tabs.tabText(i) for i in range(panel.tabs.count())],
                         ["Voice", "Wake", "Conversation", "Diagnostics"])
        self.window.toggle_developer_tools(); self.assertTrue(panel.isVisible())
        self.window.toggle_developer_tools(); self.assertFalse(panel.isVisible())

    def test_each_tab_exposes_required_controls(self):
        panel = self.window.developer_tools_panel
        for index, controls in enumerate((
            (panel.voice_start, panel.voice_stop, panel.voice_cancel, panel.microphone, panel.recognized, panel.reply),
            (panel.wake_start, panel.wake_stop, panel.simulate_wake, panel.force_sleep, panel.backend, panel.confidence),
            (panel.conversation_backend, panel.conversation_input, panel.conversation_reply,
             panel.conversation_count, panel.conversation_time, panel.clear_conversation,
             panel.hybrid_mode, panel.local_backend_status, panel.openai_backend_status,
             panel.placeholder_backend_status, panel.run_hybrid_test, panel.cancel_ai_request,
             panel.current_personality, panel.reload_personality, panel.preview_personality_prompt,
             panel.groq_backend_status, panel.groq_model, panel.groq_api_key, panel.test_groq),
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

    def test_switching_tabs_in_docked_panel_does_not_resize_main(self):
        original_size = self.window.size()
        self.window.toggle_developer_tools(); self.app.processEvents()
        for index in range(4):
            self.window.developer_tools_panel.tabs.setCurrentIndex(index); self.app.processEvents()
            self.assertEqual(self.window.size(), original_size)

    def test_close_button_reuses_panel_and_navigation_away_closes_it(self):
        panel = self.window.developer_tools_panel
        self.window.open_developer_tools(); self.app.processEvents()
        self.assertTrue(panel.isVisible()); self.assertEqual(self.window.sidebar.currentRow(), 0)
        panel.close_button.click(); self.app.processEvents(); self.assertFalse(panel.isVisible())
        self.window.open_developer_tools(); self.app.processEvents(); self.assertIs(panel, self.window.developer_tools_panel)
        self.window.sidebar.setCurrentRow(1); self.app.processEvents(); self.assertFalse(panel.isVisible())

    def test_tab_shortcuts_only_enabled_while_tools_visible(self):
        self.assertTrue(all(not shortcut.isEnabled() for shortcut in self.window._developer_tab_shortcuts))
        self.window.toggle_developer_tools(); self.app.processEvents()
        self.assertTrue(all(shortcut.isEnabled() for shortcut in self.window._developer_tab_shortcuts))
        QTest.keyClick(self.window, Qt.Key_3, Qt.ControlModifier)
        self.assertEqual(self.window.developer_tools_panel.tabs.currentIndex(), 2)
        self.window.toggle_developer_tools(); self.app.processEvents()
        self.assertTrue(all(not shortcut.isEnabled() for shortcut in self.window._developer_tab_shortcuts))

    def test_openai_test_button_reports_sanitized_success_and_failure(self):
        panel = self.window.developer_tools_panel
        panel.test_openai.setEnabled(False)
        panel._openai_test_result({"success": True, "backend": "openai", "model": "test-model",
                                   "elapsed": .125, "text": "connection successful"})
        self.assertTrue(panel.test_openai.isEnabled())
        self.assertIn("SUCCESS", panel.test_openai.toolTip())
        panel.test_openai.setEnabled(False)
        panel._openai_test_result({"success": False, "category": "auth",
                                   "message": "OpenAI authentication failed."})
        self.assertTrue(panel.test_openai.isEnabled())
        self.assertIn("Category: auth", panel.test_openai.toolTip())

    def test_developer_tools_backend_and_manager_share_resolved_openai_config(self):
        conversation = self.window.voice_manager.conversation_manager
        backend = conversation.ai_manager.backends["openai"]
        self.assertIs(conversation.ai_manager.openai_config, backend.config)
        panel = self.window.developer_tools_panel
        self.assertEqual(panel.openai_model.text(), backend.config.model)
        self.assertEqual(panel.openai_api_key.text(),
                         "configured" if backend.config.api_key_present else "missing")
        self.assertEqual(panel.openai_environment_detected.text(),
                         "yes" if backend.config.environment_detected else "no")
        self.assertEqual(panel.openai_sdk_installed.text(),
                         "yes" if backend.sdk_installed else "no")
        self.assertEqual(panel.openai_backend_enabled.text(),
                         "yes" if backend.config.enabled else "no")

    def test_developer_tools_and_manager_share_groq_config(self):
        conversation = self.window.voice_manager.conversation_manager
        backend = conversation.ai_manager.backends["groq"]
        self.assertIs(conversation.ai_manager.groq_config, backend.config)
        panel = self.window.developer_tools_panel
        self.assertEqual(panel.groq_model.text(), backend.config.model)
        self.assertEqual(panel.groq_api_key.text(), "configured" if backend.config.api_key_present else "missing")

    def test_groq_test_button_success_and_failure(self):
        panel = self.window.developer_tools_panel; panel.test_groq.setEnabled(False)
        panel._groq_test_result({"success": True, "backend": "groq", "model": "test", "elapsed": .1,
                                 "text": "success", "usage": {"total_tokens": 2}})
        self.assertTrue(panel.test_groq.isEnabled()); self.assertIn("SUCCESS", panel.test_groq.toolTip())
        panel._groq_test_result({"success": False, "category": "quota", "code": "insufficient_quota", "message": "quota"})
        self.assertIn("insufficient_quota", panel.test_groq.toolTip())


if __name__ == "__main__": unittest.main()
