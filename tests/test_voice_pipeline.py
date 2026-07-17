import unittest
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core import PresenceState, PresenceStateManager
from app.voice import (
    PlaceholderSpeechRecognizer, PlaceholderSpeechSynthesizer, SpeechRecognizer,
    SpeechSynthesizer, VoiceConfig, VoiceManager,
)
from app.ui.voice_debug_panel import VoiceDebugPanel


class VoicePipelineTests(unittest.TestCase):
    _application = None

    @classmethod
    def setUpClass(cls) -> None:
        cls._application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.states = PresenceStateManager(PresenceState.READY)
        self.recognizer = PlaceholderSpeechRecognizer()
        self.synthesizer = PlaceholderSpeechSynthesizer()
        self.voice = VoiceManager(self.states, recognizer=self.recognizer, synthesizer=self.synthesizer)

    def test_recognizer_contract_and_placeholder_lifecycle(self) -> None:
        self.assertIsInstance(self.recognizer, SpeechRecognizer)
        received = []
        self.recognizer.recognized.connect(received.append)
        self.recognizer.start()
        self.assertTrue(self.recognizer.is_listening)
        self.recognizer.submit_text("Hello")
        self.assertEqual(received, ["Hello"])
        self.assertFalse(self.recognizer.is_listening)
        self.recognizer.cancel()

    def test_synthesizer_contract(self) -> None:
        self.assertIsInstance(self.synthesizer, SpeechSynthesizer)
        self.synthesizer.speak("Hello")
        self.assertTrue(self.synthesizer.is_speaking)
        self.synthesizer.stop()
        self.assertFalse(self.synthesizer.is_speaking)

    def test_placeholder_conversation(self) -> None:
        now = datetime(2026, 7, 17, 14, 5)
        self.assertEqual(self.voice.placeholder_reply("Hello", now), "Hello. Nice to see you.")
        self.assertEqual(self.voice.placeholder_reply("Time", now), "It is 14:05.")
        self.assertEqual(self.voice.placeholder_reply("Date", now), "Today is July 17, 2026.")
        self.assertEqual(self.voice.placeholder_reply("Anything", now), "I'm ready for the next stage of my intelligence.")

    def test_voice_state_transitions_and_return_to_ready(self) -> None:
        transitions = []
        self.states.state_changed.connect(lambda old, new: transitions.append(new))
        self.assertTrue(self.voice.start_listening())
        self.recognizer.submit_text("Hello")
        self.assertEqual(self.states.current_state, PresenceState.RESPONDING)
        self.synthesizer._finish()
        self.assertEqual(self.states.current_state, PresenceState.READY)
        self.assertEqual(transitions, [PresenceState.LISTENING, PresenceState.THINKING, PresenceState.RESPONDING, PresenceState.READY])

    def test_cancellation_returns_ready(self) -> None:
        self.voice.start_listening()
        self.voice.cancel()
        self.assertEqual(self.states.current_state, PresenceState.READY)
        self.assertFalse(self.recognizer.is_listening)

    def test_error_returns_ready(self) -> None:
        errors = []
        self.voice.error.connect(errors.append)
        self.voice.start_listening()
        self.recognizer.error.emit("Input unavailable")
        self.assertEqual(errors, ["Input unavailable"])
        self.assertEqual(self.states.current_state, PresenceState.READY)

    def test_disabled_voice_does_not_change_state(self) -> None:
        disabled = VoiceManager(PresenceStateManager(PresenceState.READY), VoiceConfig(enabled=False))
        self.assertFalse(disabled.start_listening())
        self.assertEqual(disabled.state_manager.current_state, PresenceState.READY)

    def test_tts_disabled_returns_ready_after_reply(self) -> None:
        voice = VoiceManager(
            PresenceStateManager(PresenceState.READY), VoiceConfig(tts_enabled=False),
            PlaceholderSpeechRecognizer(), PlaceholderSpeechSynthesizer(),
        )
        voice.start_listening()
        voice.recognizer.submit_text("Hello")
        self.assertEqual(voice.state_manager.current_state, PresenceState.READY)

    def test_debug_enter_submits_text_and_updates_ui(self) -> None:
        panel = VoiceDebugPanel(self.voice)
        panel.show()
        transitions = []
        recognized = []
        replies = []
        self.states.state_changed.connect(lambda old, new: transitions.append(new))
        self.voice.recognized_text.connect(recognized.append)
        self.voice.reply_generated.connect(replies.append)
        panel.input.setFocus()
        panel.input.setText("Hello")
        QTest.keyClick(panel.input, Qt.Key_Return)
        self.assertEqual(panel.input.text(), "")
        self.assertEqual(recognized, ["Hello"])
        self.assertEqual(replies, ["Hello. Nice to see you."])
        self.assertEqual(panel.recognized.text(), "Hello")
        self.assertEqual(panel.reply.text(), "Hello. Nice to see you.")
        self.assertEqual(panel.listening.text(), "inactive")
        self.assertEqual(panel.speaking.text(), "active")
        self.assertEqual(self.states.current_state, PresenceState.RESPONDING)
        self.synthesizer._finish()
        self.assertEqual(panel.speaking.text(), "inactive")
        self.assertEqual(self.states.current_state, PresenceState.READY)
        self.assertEqual(
            transitions,
            [PresenceState.LISTENING, PresenceState.THINKING,
             PresenceState.RESPONDING, PresenceState.READY],
        )

    def test_debug_enter_ignores_empty_text(self) -> None:
        panel = VoiceDebugPanel(self.voice)
        panel.show()
        panel.input.setFocus()
        panel.input.setText("   ")
        QTest.keyClick(panel.input, Qt.Key_Return)
        self.assertEqual(self.states.current_state, PresenceState.READY)
        self.assertEqual(panel.recognized.text(), "\N{EM DASH}")


if __name__ == "__main__":
    unittest.main()
