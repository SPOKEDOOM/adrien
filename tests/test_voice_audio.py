import struct
import unittest
import wave

import numpy as np

from PySide6.QtWidgets import QApplication

from app.core import PresenceState, PresenceStateManager
from app.voice.audio_controller import AudioController
from app.voice.microphone_recognizer import MicrophoneSpeechRecognizer
from app.voice.piper_synthesizer import PiperSpeechSynthesizer
from app.voice.speech_recognizer import SpeechRecognizer
from app.voice.speech_synthesizer import PlaceholderSpeechSynthesizer
from app.voice.voice_config import VoiceConfig
from app.voice.voice_manager import VoiceManager
from app.ui.voice_debug_panel import VoiceDebugPanel


class FakeSTT:
    name = "fake-stt"

    def __init__(self, text="Hello", error=None):
        self.text = text
        self.error = error
        self.calls = []

    def transcribe(self, samples, sample_rate):
        self.calls.append((samples, sample_rate))
        if self.error:
            raise self.error
        return self.text


class FakeStream:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = self.closed = self.aborted = False

    def start(self): self.started = True
    def stop(self): pass
    def close(self): self.closed = True
    def abort(self): self.aborted = True


class FakeSoundDevice:
    CallbackStop = RuntimeError
    CallbackAbort = RuntimeError

    def __init__(self):
        self.stream = None

    def query_devices(self):
        return [
            {"name": "Mic", "max_input_channels": 1, "max_output_channels": 0,
             "default_samplerate": 48000},
            {"name": "Speakers", "max_input_channels": 0, "max_output_channels": 2,
             "default_samplerate": 48000},
        ]

    def InputStream(self, **kwargs):
        self.stream = FakeStream(**kwargs)
        return self.stream


class FakeMicrophoneRecognizer(SpeechRecognizer):
    backend_name = "fake microphone"

    def __init__(self):
        super().__init__()
        self.is_listening = False
        self.cancelled = False
        self.stopped = False

    def start(self):
        self.is_listening = True

    def stop(self):
        self.stopped = True
        self.is_listening = False
        self.status_changed.emit("transcribing")

    def cancel(self):
        self.cancelled = True
        self.is_listening = False


class FakeVoice:
    def synthesize_wav(self, text, target):
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(struct.pack("<hhhh", 0, 100, -100, 0))


class FakePlayback:
    def __init__(self, error=None):
        self.error = error
        self.played = False
        self.stopped = False

    def play(self, audio, rate, device=None):
        if self.error:
            raise self.error
        self.played = True

    def wait(self): pass
    def stop(self): self.stopped = True


class RealVoiceFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_audio_device_enumeration_and_selection(self):
        config = VoiceConfig()
        controller = AudioController(config, FakeSoundDevice())
        self.assertEqual([d.name for d in controller.input_devices()], ["Mic"])
        self.assertEqual([d.name for d in controller.output_devices()], ["Speakers"])
        controller.set_input_device(0)
        controller.set_output_device(1)
        self.assertEqual(controller.input_device, "Mic")
        self.assertEqual(controller.output_device, "Speakers")

    def _recognizer(self, **overrides):
        values = dict(sample_rate=100, audio_block_size=10, energy_threshold=0.1,
                      speech_start_duration=0.2, silence_stop_duration=0.2,
                      minimum_speech_duration=0.2, maximum_recording_duration=1.0)
        values.update(overrides)
        return MicrophoneSpeechRecognizer(VoiceConfig(**values), FakeSTT(), FakeSoundDevice())

    def test_recognizer_start_and_cancel_release_device(self):
        recognizer = self._recognizer()
        recognizer.start()
        stream = recognizer._stream
        self.assertTrue(stream.started)
        recognizer.cancel()
        self.assertTrue(stream.aborted)
        self.assertTrue(stream.closed)

    def test_silence_endpoint_and_stt_success(self):
        recognizer = self._recognizer()
        recognized = []
        recognizer.recognized.connect(recognized.append)
        recognizer.is_listening = True
        recognizer.process_audio_block([0.2] * 20)
        self.assertTrue(recognizer.process_audio_block([0.0] * 20))
        recognizer._begin_transcription()
        recognizer._worker.join(1)
        self.app.processEvents()
        self.assertEqual(recognized, ["Hello"])
        self.assertEqual(recognizer.stt_backend.calls[0][1], 100)

    def test_callback_receives_audio_and_reports_rms(self):
        recognizer = self._recognizer(maximum_recording_duration=2.0)
        levels = []
        recognizer.rms_changed.connect(levels.append)
        recognizer.is_listening = True
        recognizer._audio_callback(np.asarray([[0.2], [-0.2]] * 5, dtype=np.float32),
                                   10, None, None)
        self.assertEqual(recognizer._callback_count, 1)
        self.assertAlmostEqual(levels[-1], 0.2)
        self.assertEqual(len(recognizer._blocks), 1)

    def test_speech_start_and_silence_duration_reset(self):
        recognizer = self._recognizer(silence_stop_duration=0.3)
        speech = []
        recognizer.speech_changed.connect(speech.append)
        recognizer.is_listening = True
        recognizer.process_audio_block([0.2] * 20)
        self.assertTrue(recognizer.speech_detected)
        recognizer.process_audio_block([0.0] * 10)
        self.assertEqual(recognizer._silence_frames, 10)
        recognizer.process_audio_block([0.2] * 10)
        self.assertEqual(recognizer._silence_frames, 0)
        self.assertEqual(speech, [True])

    def test_manual_stop_finalizes_and_transcribes_without_vad_trigger(self):
        recognizer = self._recognizer(minimum_usable_rms=0.01)
        recognized = []
        recognizer.recognized.connect(recognized.append)
        recognizer.is_listening = True
        recognizer.process_audio_block([0.05] * 30)
        recognizer.speech_detected = False
        recognizer.stop()
        recognizer._worker.join(1)
        self.app.processEvents()
        self.assertEqual(recognized, ["Hello"])
        self.assertTrue(recognizer._manual_finalize)

    def test_cancel_discards_recording_without_stt(self):
        recognizer = self._recognizer()
        recognizer.is_listening = True
        recognizer.process_audio_block([0.2] * 20)
        recognizer.cancel()
        self.assertEqual(recognizer._blocks, [])
        self.assertEqual(recognizer.stt_backend.calls, [])

    def test_empty_and_low_level_recordings_show_useful_errors(self):
        for blocks, expected in (
            ([], "Recording was empty"),
            ([[0.0001] * 30], "No usable speech detected"),
        ):
            with self.subTest(expected=expected):
                recognizer = self._recognizer(minimum_usable_rms=0.001)
                errors = []
                recognizer.error.connect(errors.append)
                recognizer.is_listening = True
                recognizer._blocks = blocks
                recognizer._manual_finalize = True
                recognizer._begin_transcription()
                recognizer._worker.join(1)
                self.app.processEvents()
                self.assertIn(expected, errors[-1])

    def test_maximum_duration_and_minimum_speech_rejection(self):
        recognizer = self._recognizer(maximum_recording_duration=0.2)
        errors = []
        recognizer.error.connect(errors.append)
        recognizer.is_listening = True
        self.assertTrue(recognizer.process_audio_block([0.0] * 20))
        recognizer._begin_transcription()
        recognizer._worker.join(1)
        self.app.processEvents()
        self.assertIn("No usable speech detected", errors[0])

    def test_stt_error_is_emitted(self):
        recognizer = self._recognizer()
        recognizer.stt_backend = FakeSTT(error=RuntimeError("model failed"))
        errors = []
        recognizer.error.connect(errors.append)
        recognizer.is_listening = recognizer.speech_detected = True
        recognizer._speech_frames = 20
        recognizer._blocks = [[0.2] * 20]
        recognizer._begin_transcription()
        recognizer._worker.join(1)
        self.app.processEvents()
        self.assertEqual(errors, ["model failed"])

    def test_empty_stt_result_is_visible_and_manager_returns_ready(self):
        recognizer = self._recognizer()
        recognizer.stt_backend = FakeSTT(text="")
        states = PresenceStateManager(PresenceState.READY)
        manager = VoiceManager(states, recognizer=recognizer,
                               synthesizer=PlaceholderSpeechSynthesizer())
        errors = []
        manager.error.connect(errors.append)
        manager.start_listening()
        recognizer.speech_detected = True
        recognizer._speech_frames = 30
        recognizer._blocks = [[0.2] * 30]
        recognizer.stop()
        recognizer._worker.join(1)
        self.app.processEvents()
        self.assertIn("no recognized text", errors[-1])
        self.assertEqual(states.current_state, PresenceState.READY)

    def test_no_callback_watchdog_reports_error(self):
        recognizer = self._recognizer()
        errors = []
        recognizer.error.connect(errors.append)
        recognizer.is_listening = True
        recognizer._generation = 3
        recognizer._verify_audio_received(3)
        self.assertEqual(errors, ["Microphone opened, but no audio data received."])

    def test_microphone_to_reply_state_sequence_and_pause_before_tts(self):
        states = PresenceStateManager(PresenceState.READY)
        recognizer = FakeMicrophoneRecognizer()
        synthesizer = PlaceholderSpeechSynthesizer()
        manager = VoiceManager(states, recognizer=recognizer, synthesizer=synthesizer)
        transitions = []
        states.state_changed.connect(lambda old, new: transitions.append(new))
        manager.start_listening()
        recognizer.stop()
        recognizer.recognized.emit("Hello")
        self.assertFalse(recognizer.is_listening)
        self.assertEqual(states.current_state, PresenceState.RESPONDING)
        synthesizer._finish()
        self.assertEqual(transitions, [PresenceState.LISTENING, PresenceState.THINKING,
                                       PresenceState.RESPONDING, PresenceState.READY])
        manager._on_finished()  # Duplicate completion is harmless.
        self.assertEqual(states.current_state, PresenceState.READY)

    def test_pipeline_failure_and_cancellation_return_ready(self):
        states = PresenceStateManager(PresenceState.READY)
        recognizer = FakeMicrophoneRecognizer()
        manager = VoiceManager(states, recognizer=recognizer)
        manager.start_listening()
        recognizer.error.emit("device disconnected")
        self.assertEqual(states.current_state, PresenceState.READY)
        manager.start_listening()
        manager.cancel()
        self.assertEqual(states.current_state, PresenceState.READY)

    def test_debug_panel_separates_stop_and_cancel_and_updates_diagnostics(self):
        states = PresenceStateManager(PresenceState.READY)
        recognizer = FakeMicrophoneRecognizer()
        manager = VoiceManager(states, recognizer=recognizer,
                               synthesizer=PlaceholderSpeechSynthesizer())
        panel = VoiceDebugPanel(manager)
        panel.start_button.click()
        self.assertTrue(panel.stop_button.isEnabled())
        manager.rms_changed.emit(0.01234)
        manager.speech_changed.emit(True)
        manager.duration_changed.emit(1.25)
        self.assertEqual(panel.rms.text(), "0.01234")
        self.assertEqual(panel.speech_detected.text(), "yes")
        self.assertEqual(panel.recording_duration.text(), "1.25 s")
        panel.stop_button.click()
        self.assertTrue(recognizer.stopped)
        self.assertFalse(recognizer.cancelled)
        self.assertEqual(states.current_state, PresenceState.THINKING)
        manager.cancel()
        self.assertEqual(states.current_state, PresenceState.READY)

    def test_piper_success_error_and_shutdown(self):
        config = VoiceConfig(tts_voice_model="voice.onnx")
        playback = FakePlayback()
        synth = PiperSpeechSynthesizer(config, lambda path: FakeVoice(), playback)
        finished = []
        synth.finished.connect(lambda: finished.append(True))
        synth.speak("Hello")
        synth._worker.join(1)
        self.app.processEvents()
        self.assertTrue(playback.played)
        self.assertEqual(finished, [True])
        failing = PiperSpeechSynthesizer(
            config, lambda path: FakeVoice(), FakePlayback(RuntimeError("output failed")))
        errors = []
        failing.error.connect(errors.append)
        failing.speak("Hello")
        failing._worker.join(1)
        self.app.processEvents()
        self.assertIn("output failed", errors[0])
        failing.shutdown()
        self.assertFalse(failing._worker.is_alive())


if __name__ == "__main__":
    unittest.main()
