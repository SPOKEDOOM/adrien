from __future__ import annotations

import os
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.ai import AIBackend, AIBackendManager, AIConfig, AIResponse
from app.conversation import ConversationManager
from app.memory import LongTermMemoryManager
from app.settings import ApplicationSettings


class RecordingBackend(AIBackend):
    backend_name = "placeholder"
    def __init__(self): self.request = None
    def is_available(self): return True
    def generate_reply(self, request):
        self.request = request
        return AIResponse(request.request_id, "done", "placeholder")


class LongTermMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.path = os.path.join(self.directory.name, "memory.sqlite3")
        self.memory = LongTermMemoryManager(self.path)
    def tearDown(self): self.directory.cleanup()

    def wait_for(self, predicate, timeout=1000):
        deadline = time.monotonic() + timeout / 1000
        while time.monotonic() < deadline:
            self.app.processEvents(); QTest.qWait(3)
            if predicate(): return True
        return False

    def test_crud_persistence_enable_and_category_filter(self):
        item = self.memory.create("preference", "Theme", "User prefers dark mode.")
        self.assertEqual(self.memory.get(item.id).content, "User prefers dark mode.")
        updated = self.memory.update(item.id, content="User prefers light mode.", enabled=False)
        self.assertFalse(updated.enabled); self.assertEqual(len(self.memory.list(category="preference")), 1)
        reopened = LongTermMemoryManager(self.path); self.assertEqual(reopened.get(item.id).content, "User prefers light mode.")
        self.assertTrue(reopened.delete(item.id)); self.assertEqual(reopened.list(), ())

    def test_duplicate_merges_new_confirmed_wording(self):
        first = self.memory.create("preference", "Dark mode", "User prefers dark mode.")
        second = self.memory.create("preference", "Dark mode preference", "The user likes dark mode.")
        self.assertEqual(first.id, second.id); self.assertEqual(len(self.memory.list()), 1)
        self.assertEqual(second.content, "The user likes dark mode.")

    def test_candidates_approve_dismiss_and_disable_category(self):
        first = self.memory.create_candidate("identity", "Preferred name", "Call the user Providence.")
        saved = self.memory.approve_candidate(first.id); self.assertTrue(saved.user_confirmed)
        second = self.memory.create_candidate("goal", "Goal", "Build ADRIEN.")
        self.assertTrue(self.memory.dismiss_candidate(second.id))
        third = self.memory.create_candidate("routine", "Routine", "Weekly review.")
        self.assertTrue(self.memory.disable_candidate_category(third.id))
        self.assertIsNone(self.memory.create_candidate("routine", "Another", "Daily review."))

    def test_sensitive_credentials_are_rejected(self):
        for content in ("My password is hunter2", "OPENAI_API_KEY=sk-secretvalue123456",
                        "GROQ_API_KEY=gsk_secretvalue123456", "Access token: abc123"):
            with self.assertRaises(ValueError): self.memory.create("note", "Secret", content)
        self.assertEqual(self.memory.list(), ())

    def test_relevance_excludes_irrelevant_and_works_offline(self):
        blue = self.memory.create("preference", "Favourite colour", "User's favourite colour is blue.", importance=5)
        self.memory.create("tool", "Editor", "User frequently uses VS Code.")
        results = self.memory.search_relevant("What is my favourite colour?")
        self.assertEqual([item.id for item in results], [blue.id])
        self.assertEqual(self.memory.last_retrieval_count, 1)

    def test_explicit_commands_and_conversation_separation(self):
        manager = ConversationManager(long_term_memory=self.memory); replies = []; manager.reply_ready.connect(replies.append)
        self.assertTrue(manager.process("Remember that my test colour is blue."))
        self.assertTrue(self.wait_for(lambda: bool(replies))); self.assertEqual(len(self.memory.list()), 1)
        manager.clear_conversation_memory(); self.assertEqual(manager.memory.exchanges, ())
        self.assertEqual(len(self.memory.list()), 1)
        manager.process("What do you remember about my test colour?")
        self.assertTrue(self.wait_for(lambda: len(replies) == 2)); self.assertIn("blue", replies[-1])
        manager.process("Forget my test colour")
        self.assertTrue(self.wait_for(lambda: len(replies) == 3)); self.assertEqual(self.memory.list(), ())
        manager.shutdown()

    def test_restart_edit_and_honest_offline_recall(self):
        first = ConversationManager(long_term_memory=self.memory); replies = []; first.reply_ready.connect(replies.append)
        first.process("Remember that my test colour is blue."); self.assertTrue(self.wait_for(lambda: bool(replies))); first.shutdown()
        reopened = LongTermMemoryManager(self.path); second = ConversationManager(long_term_memory=reopened)
        answers = []; second.reply_ready.connect(answers.append); second.process("What is my test colour?")
        self.assertTrue(self.wait_for(lambda: bool(answers))); self.assertIn("blue", answers[-1])
        saved = reopened.list()[0]; reopened.update(saved.id, content="My test colour is green.")
        second.process("What is my test colour?"); self.assertTrue(self.wait_for(lambda: len(answers) == 2)); self.assertIn("green", answers[-1])
        reopened.delete(saved.id); second.process("What is my test colour?")
        self.assertTrue(self.wait_for(lambda: len(answers) == 3)); self.assertIn("don't have", answers[-1]); second.shutdown()

    def test_clear_long_term_does_not_clear_conversation(self):
        manager = ConversationManager(long_term_memory=self.memory)
        manager.memory.add_exchange("temporary", "context"); self.memory.create("note", "Saved", "Persistent fact")
        self.memory.clear(); self.assertEqual(len(manager.memory.exchanges), 1); self.assertEqual(self.memory.list(), ())
        manager.shutdown()

    def test_prompt_injects_only_relevant_memory(self):
        self.memory.create("project", "ADRIEN", "The user is building ADRIEN's memory system.", importance=5)
        self.memory.create("preference", "Food", "The user likes mangoes.")
        backend = RecordingBackend(); ai = AIBackendManager(AIConfig(hybrid_mode="placeholder_only", fallback_enabled=False))
        ai.register_backend(backend)
        manager = ConversationManager(ai_manager=ai, long_term_memory=self.memory); replies = []; manager.reply_ready.connect(replies.append)
        manager.process("Continue the ADRIEN memory system project")
        self.assertTrue(self.wait_for(lambda: bool(replies)))
        self.assertIn("Relevant Long-Term Memory", backend.request.system_prompt)
        self.assertIn("ADRIEN's memory system", backend.request.system_prompt)
        self.assertNotIn("mangoes", backend.request.system_prompt); manager.shutdown()

    def test_configuration_persistence(self):
        path = os.path.join(self.directory.name, "settings.ini"); settings = ApplicationSettings(QSettings(path, QSettings.IniFormat))
        settings.set_value("memory/long_term_enabled", False); settings.set_value("memory/suggestions_enabled", False)
        settings.set_value("memory/ask_before_saving", False); settings.set_value("memory/maximum_memories", 123)
        settings.set_value("memory/disabled_suggestion_categories", ["identity", "goal"])
        restored = ApplicationSettings(QSettings(path, QSettings.IniFormat))
        self.assertFalse(restored.long_term_memory_enabled); self.assertFalse(restored.memory_suggestions_enabled)
        self.assertFalse(restored.memory_ask_before_saving); self.assertEqual(restored.maximum_long_term_memories, 123)
        self.assertEqual(restored.disabled_memory_suggestion_categories, ("identity", "goal"))


if __name__ == "__main__": unittest.main()
