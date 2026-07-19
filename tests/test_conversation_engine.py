from __future__ import annotations

import threading
import time
import unittest
from datetime import datetime

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.conversation import (
    ConversationBackend, ConversationConfig, ConversationContext,
    ConversationManager, PlaceholderBackend,
)
from app.core import PresenceState, PresenceStateManager
from app.ui.developer_tools_panel import DeveloperToolsPanel
from app.voice import PlaceholderSpeechRecognizer, PlaceholderSpeechSynthesizer, VoiceManager
from app.wake import WakeManager


class ReplacementBackend(ConversationBackend):
    name = "replacement"
    def __init__(self, delay=0.0, failure=None):
        self.delay, self.failure = delay, failure
        self.initialized = self.stopped = False
        self.thread_id = None
    def initialize(self): self.initialized = True
    def generate_reply(self, text, context):
        self.thread_id = threading.get_ident()
        if self.delay: time.sleep(self.delay)
        if self.failure: raise self.failure
        return f"replacement: {text} ({context.interaction_count})"
    def shutdown(self): self.stopped = True


class ConversationEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_for(self, predicate, timeout=1000):
        deadline = time.monotonic() + timeout / 1000
        while time.monotonic() < deadline:
            self.app.processEvents(); QTest.qWait(2)
            if predicate(): return True
        return False

    def test_placeholder_known_and_unknown_responses(self):
        now = datetime(2026, 7, 18, 10, 5)
        backend = PlaceholderBackend(clock=lambda: now); backend.initialize()
        context = ConversationContext()
        self.assertEqual(backend.generate_reply("Hello", context), "Hello. Nice to see you.")
        self.assertEqual(backend.generate_reply("How are you?", context), "I'm functioning normally. Thank you for asking.")
        self.assertEqual(backend.generate_reply("What time is it?", context), "It is 10:05.")
        self.assertEqual(backend.generate_reply("Who created you?", context), "I am ADRIEN, currently under development.")
        self.assertEqual(backend.generate_reply("Explain gravity", context), "I understood your request, but I cannot answer that yet.")

    def test_context_trims_to_last_ten_but_counts_all(self):
        context = ConversationContext(10)
        for index in range(14): context.add_exchange(f"u{index}", f"a{index}")
        self.assertEqual(len(context.exchanges), 10)
        self.assertEqual(context.recent_user_messages[0], "u4")
        self.assertEqual(context.interaction_count, 14)

    def test_empty_input_is_rejected_without_worker(self):
        manager = ConversationManager()
        errors = []; manager.error.connect(errors.append)
        self.assertFalse(manager.process("   "))
        self.assertFalse(manager.is_processing); self.assertTrue(errors)
        manager.shutdown()

    def test_backend_replacement_runs_off_gui_thread_and_updates_context(self):
        backend = ReplacementBackend()
        manager = ConversationManager(backend=backend)
        replies = []; manager.reply_ready.connect(replies.append)
        gui_thread = threading.get_ident()
        self.assertTrue(manager.process("hello"))
        self.assertTrue(self.wait_for(lambda: bool(replies)))
        self.assertEqual(replies, ["replacement: hello (0)"])
        self.assertNotEqual(backend.thread_id, gui_thread)
        self.assertEqual(manager.context.interaction_count, 1)
        manager.shutdown(); self.assertTrue(backend.stopped)

    def test_timeout_emits_friendly_reply_and_ignores_late_worker(self):
        backend = ReplacementBackend(delay=.12)
        manager = ConversationManager(ConversationConfig(processing_timeout_seconds=.02), backend)
        replies = []; errors = []
        manager.reply_ready.connect(replies.append); manager.error.connect(errors.append)
        manager.process("slow")
        self.assertTrue(self.wait_for(lambda: bool(replies)))
        self.assertIn("too long", replies[0]); self.assertTrue(errors)
        time.sleep(.14); self.app.processEvents()
        self.assertEqual(len(replies), 1); self.assertEqual(manager.context.interaction_count, 0)
        manager.shutdown()

    def test_backend_failure_and_worker_cleanup(self):
        backend = ReplacementBackend(failure=RuntimeError("boom"))
        manager = ConversationManager(backend=backend)
        replies = []; manager.reply_ready.connect(replies.append)
        manager.process("fail")
        self.assertTrue(self.wait_for(lambda: bool(replies)))
        self.assertEqual(replies, ["I could not process that request."])
        manager.shutdown()
        self.assertFalse(manager._worker and manager._worker.is_alive())

    def test_newer_request_ignores_stale_older_response(self):
        class VariableBackend(ReplacementBackend):
            def generate_reply(self, text, context):
                if text == "old": time.sleep(.10)
                return f"reply: {text}"
        manager = ConversationManager(backend=VariableBackend())
        replies = []; manager.reply_ready.connect(replies.append)
        manager.process("old"); time.sleep(.01); manager.process("new")
        self.assertTrue(self.wait_for(lambda: bool(replies)))
        time.sleep(.12); self.app.processEvents()
        self.assertEqual(replies, ["reply: new"])
        self.assertEqual(manager.context.recent_user_messages, ("new",))
        manager.shutdown()

    def test_slow_backend_does_not_block_process_call(self):
        manager = ConversationManager(backend=ReplacementBackend(delay=.08))
        started = time.monotonic(); self.assertTrue(manager.process("responsive"))
        self.assertLess(time.monotonic() - started, .04)
        manager.shutdown()

    def test_developer_tools_receive_conversation_diagnostics(self):
        states = PresenceStateManager(PresenceState.READY)
        voice = VoiceManager(states, recognizer=PlaceholderSpeechRecognizer(),
                             synthesizer=PlaceholderSpeechSynthesizer())
        wake = WakeManager(states, voice, voice.audio_controller)
        panel = DeveloperToolsPanel(wake, voice)
        voice.submit_debug_text("Who created you?")
        self.assertTrue(self.wait_for(lambda: voice.conversation_manager.context.interaction_count == 1))
        self.assertEqual(panel.conversation_backend.text(), "placeholder")
        self.assertEqual(panel.conversation_input.text(), "Who created you?")
        self.assertEqual(panel.conversation_reply.text(), "I am ADRIEN, currently under development.")
        self.assertEqual(panel.conversation_count.text(), "1")
        self.assertEqual(panel.conversation_status.text(), "ready")
        wake.shutdown(); voice.shutdown()


if __name__ == "__main__": unittest.main()
