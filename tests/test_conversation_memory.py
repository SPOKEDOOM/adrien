from __future__ import annotations

import os
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.conversation import ConversationConfig, ConversationManager, ConversationMemory
from app.personality import PersonalityManager, PromptBuilder
from app.settings import ApplicationSettings
from app.ui.developer_tools_panel import DeveloperToolsPanel
from app.core import PresenceState, PresenceStateManager
from app.voice import PlaceholderSpeechRecognizer, PlaceholderSpeechSynthesizer, VoiceManager
from app.wake import WakeManager


class ConversationMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def wait_for(self, predicate, timeout=1500):
        deadline = time.monotonic() + timeout / 1000
        while time.monotonic() < deadline:
            self.app.processEvents(); QTest.qWait(3)
            if predicate(): return True
        return False

    def test_append_summary_trimming_and_reset(self):
        memory = ConversationMemory(4, 4, 50, True)
        for index in range(4): memory.add_exchange(f"request {index}", f"reply {index}")
        represented = memory.summary_candidates(); self.assertEqual(len(represented), 2)
        memory.apply_summary(memory.deterministic_summary(represented), represented)
        self.assertEqual(memory.recent_message_count, 4); self.assertIsNotNone(memory.summary)
        self.assertEqual(memory.summary.message_count_represented, 4)
        self.assertIn("request 0", memory.summary.text)
        memory.clear(); self.assertEqual(memory.exchanges, ()); self.assertIsNone(memory.summary)

    def test_summary_length_is_bounded(self):
        memory = ConversationMemory(2, 2, 20, True); memory.add_exchange("one", "two")
        represented = memory.summary_candidates(force=True)
        memory.apply_summary("word " * 100, represented)
        self.assertLessEqual(len(memory.summary.text.split()), 20)

    def test_prompt_assembles_summary_before_recent_history(self):
        memory = ConversationMemory(2, 2, 100, True)
        memory.add_exchange("old goal", "old commitment")
        represented = memory.summary_candidates(force=True)
        memory.apply_summary("The user has an unfinished project goal.", represented)
        memory.add_exchange("recent request", "recent reply")
        personality = PersonalityManager(); prompt = PromptBuilder().build_prompt(personality.profile, memory)
        self.assertIn("Conversation summary (older context):", prompt)
        self.assertIn("unfinished project goal", prompt)

    def test_offline_force_summary_runs_asynchronously(self):
        config = ConversationConfig(maximum_recent_messages=2, summary_threshold=2)
        manager = ConversationManager(config); manager.set_hybrid_mode("placeholder_only")
        manager.memory.add_exchange("Build ADRIEN memory", "I will implement it")
        started = time.monotonic(); self.assertTrue(manager.force_summary())
        self.assertLess(time.monotonic() - started, .05)
        self.assertTrue(self.wait_for(lambda: manager.memory.summary is not None))
        self.assertIn("Build ADRIEN memory", manager.memory.summary.text)
        manager.shutdown()

    def test_memory_configuration_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "settings.ini"); settings = ApplicationSettings(QSettings(path, QSettings.IniFormat))
            settings.set_value("memory/maximum_recent_messages", 40)
            settings.set_value("memory/summary_threshold", 36)
            settings.set_value("memory/maximum_summary_words", 250)
            settings.set_value("memory/conversation_summaries_enabled", False)
            restored = ApplicationSettings(QSettings(path, QSettings.IniFormat))
            self.assertEqual(restored.memory_maximum_recent_messages, 40)
            self.assertEqual(restored.memory_summary_threshold, 36)
            self.assertEqual(restored.memory_maximum_summary_words, 250)
            self.assertFalse(restored.memory_summaries_enabled)

    def test_developer_tools_memory_actions_and_diagnostics(self):
        states = PresenceStateManager(PresenceState.READY)
        voice = VoiceManager(states, recognizer=PlaceholderSpeechRecognizer(),
                             synthesizer=PlaceholderSpeechSynthesizer())
        wake = WakeManager(states, voice, voice.audio_controller); panel = DeveloperToolsPanel(wake, voice)
        voice.conversation_manager.memory.add_exchange("remember this", "acknowledged")
        voice.conversation_manager._emit_diagnostics(); self.app.processEvents()
        self.assertEqual(panel.memory_recent_messages.text(), "2")
        panel.force_memory_summary.click()
        self.assertTrue(self.wait_for(lambda: panel.memory_summary_exists.text() == "yes"))
        panel.clear_conversation_memory.click(); self.app.processEvents()
        self.assertEqual(panel.memory_recent_messages.text(), "0")
        self.assertEqual(panel.memory_summary_exists.text(), "no")
        wake.shutdown(); voice.shutdown()


if __name__ == "__main__": unittest.main()
