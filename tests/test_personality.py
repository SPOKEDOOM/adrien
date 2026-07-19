from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.ai import AIBackend, AIBackendManager, AIConfig, AIResponse
from app.conversation import ConversationContext, ConversationManager, PlaceholderBackend
from app.personality import PersonalityConfig, PersonalityManager, PersonalityValidationError, PromptBuilder, TraitRegistry


class CapturingBackend(AIBackend):
    backend_name = "placeholder"

    def __init__(self): self.request = None
    def is_available(self): return True
    def generate_reply(self, request):
        self.request = request
        return AIResponse(text="captured", backend_used=self.backend_name)


class PersonalityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def wait_for(self, predicate, timeout=1000):
        deadline = time.monotonic() + timeout / 1000
        while time.monotonic() < deadline:
            self.app.processEvents(); QTest.qWait(2)
            if predicate(): return True
        return False

    def test_default_profile_loads_and_validates(self):
        manager = PersonalityManager()
        self.assertEqual(manager.profile.name, "ADRIEN")
        self.assertIn("Assist the user", manager.profile.mission)
        self.assertEqual(manager.profile.traits, ("assistant", "friendly", "technical"))

    def test_invalid_profile_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps({"mission": ""}), encoding="utf-8")
            with self.assertRaises(PersonalityValidationError):
                PersonalityManager(PersonalityConfig(profile_path=str(path)))

    def test_traits_are_composable_and_unknown_traits_fail(self):
        registry = TraitRegistry()
        self.assertEqual([t.name for t in registry.compose(("friendly", "technical", "friendly"))],
                         ["friendly", "technical"])
        with self.assertRaises(ValueError): registry.compose(("not-a-trait",))

    def test_prompt_combines_identity_context_configuration_and_task(self):
        manager = PersonalityManager(); context = ConversationContext()
        context.add_exchange("Hello", "Hello.")
        prompt = PromptBuilder().build_prompt(manager.profile, context, {"backend": "placeholder"}, "Answer safely")
        self.assertIn("Identity: You are ADRIEN.", prompt)
        self.assertIn("assistant:", prompt)
        self.assertIn("1 recent exchanges", prompt)
        self.assertIn("Task instructions: Answer safely", prompt)

    def test_live_reload_updates_profile_and_emits_signal(self):
        source = Path(__file__).parents[1] / "app" / "personality" / "default_profile.json"
        values = json.loads(source.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"; path.write_text(json.dumps(values), encoding="utf-8")
            manager = PersonalityManager(PersonalityConfig(profile_path=str(path)))
            changed = []; manager.personality_changed.connect(changed.append)
            values["mission"] = "A newly reloaded mission."
            path.write_text(json.dumps(values), encoding="utf-8")
            self.assertTrue(manager.reload())
            self.assertEqual(manager.profile.mission, "A newly reloaded mission.")
            self.assertEqual(changed[-1], manager.profile)

    def test_placeholder_responses_reflect_identity(self):
        backend = PlaceholderBackend(); context = ConversationContext(); personality = {"name": "NOVA"}
        self.assertEqual(backend.generate_reply("Who are you?", context, personality),
                         "I'm NOVA, your desktop AI assistant.")
        self.assertEqual(backend.generate_reply("Can you do everything?", context, personality),
                         "Not yet. I'm still under active development.")

    def test_conversation_sends_personality_prompt_to_backend(self):
        backend = CapturingBackend()
        ai_manager = AIBackendManager(config=AIConfig(hybrid_mode="placeholder_only"))
        ai_manager.register_backend(backend); ai_manager.initialize()
        manager = ConversationManager(ai_manager=ai_manager)
        replies = []; manager.reply_ready.connect(replies.append)
        self.assertTrue(manager.process("Hello")); self.assertTrue(self.wait_for(lambda: bool(replies)))
        self.assertIn("Identity: You are ADRIEN.", backend.request.system_prompt)
        self.assertEqual(backend.request.metadata["personality"]["name"], "ADRIEN")
        manager.shutdown()


if __name__ == "__main__": unittest.main()
