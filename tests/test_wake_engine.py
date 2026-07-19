import time
import unittest

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import QTimer

from app.core import PresenceState, PresenceStateManager
from app.ui.wake_debug_panel import WakeDebugPanel
from app.ui.main_window import MainWindow
from app.voice import PlaceholderSpeechRecognizer, PlaceholderSpeechSynthesizer, VoiceConfig, VoiceManager
from app.voice.audio_controller import AudioMode
from app.wake import DevelopmentWakeBackend, WakeConfig, WakeDetector, WakeManager
from app.wake.audio_ring_buffer import AudioRingBuffer
from app.wake.wake_backend import WakeBackend


class FailingBackend(WakeBackend):
    name = "failing production"

    def start(self):
        self.error.emit("backend unavailable")

    def stop(self):
        pass


class WakeEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.states = PresenceStateManager(PresenceState.SLEEP)
        self.recognizer = PlaceholderSpeechRecognizer()
        self.synthesizer = PlaceholderSpeechSynthesizer()
        self.voice = VoiceManager(
            self.states, VoiceConfig(), self.recognizer, self.synthesizer
        )
        self.backend = DevelopmentWakeBackend()
        self.config = WakeConfig(wake_decision_delay_ms=0, wake_cooldown_seconds=2.0,
                                 wake_command_timeout_seconds=0.05,
                                 ready_before_sleep_seconds=0.01,
                                 wake_acknowledgement_enabled=True)
        self.wake = WakeManager(self.states, self.voice, self.voice.audio_controller,
                                self.config, self.backend)

    def tearDown(self):
        self.wake.shutdown()

    def _accept_and_materialize(self):
        self.wake.start()
        self.wake.simulate(0.95)
        self.wake._decision_timer.stop()
        self.wake._begin_materialization()
        self.assertEqual(self.states.current_state, PresenceState.MATERIALIZING)

    def _reach_command_listening(self):
        self._accept_and_materialize()
        self.states.transition_to(PresenceState.READY)
        self.wake._ack_timer.stop()
        self.wake._begin_acknowledgement()
        self.assertEqual(self.voice.audio_controller.mode, AudioMode.TTS_PLAYBACK)
        self.synthesizer._finish()
        self.assertEqual(self.states.current_state, PresenceState.LISTENING)

    def test_start_stop_and_repeated_cycles_are_idempotent(self):
        changes = []
        self.wake.monitoring_changed.connect(changes.append)
        self.wake.start()
        self.wake.start()
        self.assertTrue(self.wake.running)
        self.assertTrue(self.wake.monitoring)
        self.assertEqual(self.voice.audio_controller.mode, AudioMode.IDLE)
        self.wake.stop()
        self.wake.stop()
        self.assertEqual(changes, [True, False])
        self.assertEqual(self.voice.audio_controller.mode, AudioMode.IDLE)

    def test_high_confidence_accepted_and_low_rejected(self):
        decisions = []
        self.wake.candidate_evaluated.connect(
            lambda result, accepted, reason: decisions.append((result, accepted, reason)))
        self.wake.start()
        self.wake.simulate(0.40)
        self.assertFalse(decisions[-1][1])
        self.assertEqual(decisions[-1][2], "confidence below threshold")
        self.wake.simulate(0.95)
        self.assertTrue(decisions[-1][1])
        self.assertTrue(self.wake.handling_wake)

    def test_confidence_clamped_and_phrase_normalized(self):
        results = []
        detector = WakeDetector(self.backend, self.config)
        detector.candidate.connect(results.append)
        self.backend.start()
        self.backend.inject("  HEY   ADRIEN ", 4.0)
        self.assertEqual(results[-1].confidence, 1.0)
        self.assertTrue(detector.phrase_matches(results[-1].phrase))
        self.assertFalse(detector.phrase_matches("adrenaline"))

    def test_wake_ignored_outside_sleep(self):
        self.states.transition_to_for_development(PresenceState.READY)
        self.wake.start()
        self.assertFalse(self.wake.monitoring)
        self.wake.simulate(0.95)
        self.assertFalse(self.wake.handling_wake)

    def test_duplicate_and_cooldown_are_suppressed(self):
        accepted = []
        self.wake.wake_detected.connect(accepted.append)
        self.wake.start()
        self.wake.simulate(0.95)
        self.backend.start()  # Simulate a stale backend callback.
        self.backend.inject("Adrien", 0.99)
        self.assertEqual(len(accepted), 1)
        self.wake.handling_wake = False
        self.wake.monitoring = True
        self.backend.inject("Adrien", 0.99)
        self.assertEqual(len(accepted), 1)

    def test_wake_sequence_acknowledgement_and_command_audio_ownership(self):
        self._reach_command_listening()
        self.assertEqual(self.synthesizer.last_text, "Yes?")
        self.assertEqual(self.wake.phase, "command")
        self.assertEqual(self.voice.audio_controller.mode, AudioMode.COMMAND_LISTENING)
        self.assertFalse(self.wake.monitoring)

    def test_command_timeout_returns_to_sleep_and_resumes_monitoring(self):
        self._reach_command_listening()
        self.wake._command_timer.stop()
        self.wake._command_timeout()
        self.assertEqual(self.states.current_state, PresenceState.SLEEP)
        self.assertTrue(self.wake.monitoring)
        self.assertEqual(self.voice.audio_controller.mode, AudioMode.IDLE)

    def test_successful_response_returns_to_sleep(self):
        self._reach_command_listening()
        self.voice.submit_debug_text("Hello")
        deadline = time.monotonic() + 1
        while (time.monotonic() < deadline and
               self.voice.conversation_manager.context.interaction_count == 0):
            self.app.processEvents()
            if self.voice.conversation_manager.context.interaction_count == 0:
                time.sleep(.002)
        self.assertIn(self.states.current_state, (PresenceState.RESPONDING, PresenceState.READY))
        if self.states.current_state is PresenceState.RESPONDING:
            self.synthesizer._finish()
        self.assertEqual(self.states.current_state, PresenceState.READY)
        self.wake._sleep_timer.stop()
        self.wake._return_to_sleep()
        self.assertEqual(self.states.current_state, PresenceState.SLEEP)
        self.assertTrue(self.wake.monitoring)

    def test_backend_failure_uses_development_fallback(self):
        wake = WakeManager(self.states, self.voice, self.voice.audio_controller,
                           self.config, FailingBackend())
        wake.start()
        self.assertIsInstance(wake.backend, DevelopmentWakeBackend)
        self.assertTrue(wake.running)
        self.assertTrue(wake.monitoring)
        wake.shutdown()

    def test_shutdown_cleans_timers_and_backend(self):
        self.wake.start()
        self.wake.simulate(0.95)
        self.wake.shutdown()
        self.assertFalse(self.wake.running)
        self.assertFalse(self.backend.active)
        self.assertFalse(self.wake._decision_timer.isActive())
        self.assertFalse(self.wake._ticker.isActive())

    def test_ring_buffer_is_bounded(self):
        buffer = AudioRingBuffer(3)
        buffer.append([1, 2, 3, 4])
        self.assertEqual(buffer.snapshot(), (2.0, 3.0, 4.0))
        buffer.clear()
        self.assertEqual(len(buffer), 0)

    def test_debug_panel_controls_and_diagnostics(self):
        panel = WakeDebugPanel(self.wake)
        panel.start_button.click()
        panel.low_button.click()
        self.assertEqual(panel.last_confidence.text(), "0.40")
        self.assertIn("rejected", panel.engine_status.text())
        panel.sleep_button.click()
        self.assertEqual(self.states.current_state, PresenceState.SLEEP)

    def test_acknowledgement_disabled_starts_listening_without_tts(self):
        self.config.wake_acknowledgement_enabled = False
        self._accept_and_materialize()
        self.states.transition_to(PresenceState.READY)
        self.wake._ack_timer.stop()
        self.wake._begin_acknowledgement()
        self.assertEqual(self.synthesizer.last_text, "")
        self.assertEqual(self.states.current_state, PresenceState.LISTENING)
        self.assertEqual(self.voice.audio_controller.mode, AudioMode.COMMAND_LISTENING)

    def test_simulate_wake_async_sequence_is_responsive_and_opens_capture_last(self):
        self.config.wake_acknowledgement_enabled = False
        self.config.wake_materialization_duration_ms = 5
        self.config.wake_command_timeout_seconds = 1.0
        responsive = []
        QTimer.singleShot(1, lambda: responsive.append(True))
        self.wake.start()
        self.wake.simulate(0.95)
        self.assertFalse(self.recognizer.is_listening)
        QTest.qWait(250)
        self.assertEqual(responsive, [True])
        self.assertEqual(self.states.current_state, PresenceState.LISTENING)
        self.assertTrue(self.recognizer.is_listening)
        self.assertEqual(self.voice.audio_controller.mode, AudioMode.COMMAND_LISTENING)

    def test_three_repeated_fallback_wake_cycles_emit_once_each(self):
        self.config.wake_acknowledgement_enabled = False
        self.config.wake_materialization_duration_ms = 1
        self.config.wake_cooldown_seconds = 0.0
        self.config.wake_command_timeout_seconds = 1.0
        accepted = []
        self.wake.wake_detected.connect(accepted.append)
        self.wake.start()
        for cycle in range(3):
            self.wake.simulate(0.95)
            QTest.qWait(180)
            self.assertEqual(self.states.current_state, PresenceState.LISTENING)
            self.wake._command_timer.stop()
            self.wake._command_timeout()
            self.assertEqual(self.states.current_state, PresenceState.SLEEP)
        self.assertEqual(len(accepted), 3)

    def test_developer_tools_hidden_and_toggle_without_cluttering_central_layout(self):
        window = MainWindow()
        self.assertFalse(window.developer_dock.isVisible())
        central_layout = window.centralWidget().layout()
        self.assertEqual(central_layout.count(), 2)  # Sidebar and core only.
        window.show()
        self.app.processEvents()
        window.toggle_developer_tools()
        self.assertTrue(window.developer_dock.isVisible())
        self.assertLessEqual(window.developer_dock.maximumWidth(), 380)
        window.toggle_developer_tools()
        self.assertFalse(window.developer_dock.isVisible())
        window.close()


if __name__ == "__main__":
    unittest.main()
