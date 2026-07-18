from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer, Signal

from app.core import PresenceState, PresenceStateManager
from app.voice.audio_controller import AudioController, AudioMode
from app.voice.voice_manager import VoiceManager
from app.wake.wake_backend import DevelopmentWakeBackend, WakeBackend
from app.wake.wake_config import WakeConfig
from app.wake.wake_detector import WakeDetector, WakeResult


class WakeManager(QObject):
    """Coordinates wake decisions without rendering or microphone implementation details."""

    wake_detected = Signal(object)
    candidate_evaluated = Signal(object, bool, str)
    status_changed = Signal(str)
    monitoring_changed = Signal(bool)
    error = Signal(str)
    cooldown_changed = Signal(float)
    command_timeout_changed = Signal(float)
    backend_changed = Signal(str)

    def __init__(
        self, state_manager: PresenceStateManager, voice_manager: VoiceManager,
        audio_controller: AudioController, config: WakeConfig | None = None,
        backend: WakeBackend | None = None,
    ) -> None:
        super().__init__()
        self.state_manager = state_manager
        self.voice_manager = voice_manager
        self.audio_controller = audio_controller
        self.config = config or WakeConfig()
        self.backend = backend or DevelopmentWakeBackend()
        self.detector = WakeDetector(self.backend, self.config)
        self.running = False
        self.monitoring = False
        self.handling_wake = False
        self.shutting_down = False
        self.phase = "idle"
        self.last_result: WakeResult | None = None
        self._cooldown_until = 0.0
        self._command_deadline = 0.0
        self._decision_timer = self._single_shot(self._begin_materialization)
        self._materialization_timer = self._single_shot(self._complete_wake_materialization)
        self._ack_timer = self._single_shot(self._begin_acknowledgement)
        self._command_timer = self._single_shot(self._command_timeout)
        self._sleep_timer = self._single_shot(self._return_to_sleep)
        self._ticker = QTimer(self)
        self._ticker.setInterval(100)
        self._ticker.timeout.connect(self._emit_remaining_times)
        self._connect_detector()
        state_manager.state_changed.connect(self._on_state_changed)
        voice_manager.recognized_text.connect(self._on_command_recognized)
        voice_manager.error.connect(self._on_voice_error)
        voice_manager.synthesizer.finished.connect(self._on_acknowledgement_finished)

    def _single_shot(self, callback) -> QTimer:
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        return timer

    def _connect_detector(self) -> None:
        self.detector.candidate.connect(self._on_candidate)
        self.detector.error.connect(self._on_backend_error)
        self.detector.status_changed.connect(self.status_changed)

    @property
    def backend_name(self) -> str:
        return self.backend.name

    @property
    def cooldown_remaining(self) -> float:
        return max(0.0, self._cooldown_until - time.monotonic())

    @property
    def command_timeout_remaining(self) -> float:
        return max(0.0, self._command_deadline - time.monotonic()) if self._command_timer.isActive() else 0.0

    def start(self) -> None:
        if self.running or not self.config.wake_enabled:
            return
        print("Wake engine starting", flush=True)
        print(f"Wake backend: {self.backend_name}", flush=True)
        self.running = True
        self._ticker.start()
        self.backend_changed.emit(self.backend_name)
        self.status_changed.emit("started")
        if self._state_allows_monitoring():
            self._start_monitoring()

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        self._stop_monitoring()
        for timer in (self._decision_timer, self._materialization_timer, self._ack_timer, self._command_timer,
                      self._sleep_timer, self._ticker):
            timer.stop()
        self.handling_wake = False
        self.phase = "idle"
        self.status_changed.emit("stopped")

    def _state_allows_monitoring(self) -> bool:
        state = self.state_manager.current_state
        return state is PresenceState.SLEEP or (
            self.config.wake_allow_during_ready and state is PresenceState.READY
        )

    def _start_monitoring(self) -> None:
        if not self.running or self.monitoring or not self._state_allows_monitoring():
            return
        # The simulation backend owns no microphone and leaves real audio IDLE.
        if not isinstance(self.backend, DevelopmentWakeBackend):
            self.audio_controller.set_mode(AudioMode.WAKE_MONITORING)
        self.monitoring = True
        active_backend = self.backend
        self.backend.start()
        if self.backend is not active_backend or not self.monitoring:
            return
        self.phase = "monitoring"
        print("Wake monitoring active", flush=True)
        self.monitoring_changed.emit(True)
        self.status_changed.emit("monitoring")

    def _stop_monitoring(self) -> None:
        if self.monitoring:
            self.backend.stop()
            self.monitoring = False
            self.monitoring_changed.emit(False)
        if self.audio_controller.mode is AudioMode.WAKE_MONITORING:
            self.audio_controller.set_mode(AudioMode.IDLE)

    def simulate(self, confidence: float = 0.95, phrase: str | None = None) -> None:
        inject = getattr(self.backend, "inject", None)
        if callable(inject):
            inject(phrase or self.config.wake_phrase, confidence)

    def _on_candidate(self, result: WakeResult) -> None:
        self.last_result = result
        print(f"Wake candidate detected: {result.phrase}", flush=True)
        print(f"Wake confidence: {result.confidence:.2f}", flush=True)
        reason = ""
        if not self.running or not self.monitoring:
            reason = "monitoring inactive"
        elif not self._state_allows_monitoring():
            reason = "invalid presence state"
        elif self.handling_wake:
            reason = "wake already in progress"
        elif self.cooldown_remaining > 0:
            reason = "cooldown active"
        elif not self.detector.phrase_matches(result.phrase):
            reason = "phrase mismatch"
        elif result.confidence < self.config.wake_confidence_threshold:
            reason = "confidence below threshold"
        if reason:
            print(f"Wake candidate rejected: phrase={result.phrase} "
                  f"confidence={result.confidence:.2f} reason={reason}", flush=True)
            self.candidate_evaluated.emit(result, False, reason)
            return
        print("Wake accepted", flush=True)
        self._sleep_timer.stop()
        self._ack_timer.stop()
        self._command_timer.stop()
        self.candidate_evaluated.emit(result, True, "accepted")
        self.wake_detected.emit(result)
        self.handling_wake = True
        self.phase = "decision"
        self._cooldown_until = time.monotonic() + self.config.wake_cooldown_seconds
        print("Wake cooldown started", flush=True)
        self._stop_monitoring()
        self._decision_timer.start(max(0, self.config.wake_decision_delay_ms))

    def _begin_materialization(self) -> None:
        if not self.handling_wake or self.state_manager.current_state is not PresenceState.SLEEP:
            self._stabilize_after_error("Wake sequence could not start from the current state.")
            return
        self.phase = "materializing"
        self.status_changed.emit("materializing")
        if self.state_manager.transition_to(PresenceState.MATERIALIZING):
            self._materialization_timer.start(
                max(1, self.config.wake_materialization_duration_ms)
            )

    def _complete_wake_materialization(self) -> None:
        if (self.handling_wake and self.phase == "materializing" and
                self.state_manager.current_state is PresenceState.MATERIALIZING):
            self.state_manager.transition_to(PresenceState.READY)

    def _on_state_changed(self, previous, current) -> None:
        if current is PresenceState.SLEEP:
            if self.running and not self.handling_wake:
                self._start_monitoring()
            return
        if self.monitoring and not self._state_allows_monitoring():
            self._stop_monitoring()
        if current is PresenceState.READY:
            if self.handling_wake and self.phase == "materializing":
                self._materialization_timer.stop()
                self.phase = "ack_pending"
                self._ack_timer.start(100)
            elif self.phase in ("conversation", "command_failed"):
                self.phase = "ready_before_sleep"
                delay = max(0, round(self.config.ready_before_sleep_seconds * 1000))
                self._sleep_timer.start(delay)

    def _begin_acknowledgement(self) -> None:
        if not self.handling_wake or self.state_manager.current_state is not PresenceState.READY:
            return
        if not self.config.wake_acknowledgement_enabled:
            self._start_command_listening()
            return
        self.phase = "acknowledging"
        self.audio_controller.set_mode(AudioMode.TTS_PLAYBACK)
        print("Wake acknowledgement started", flush=True)
        self.status_changed.emit("acknowledging")
        self.voice_manager.synthesizer.speak(self.config.wake_acknowledgement_text)

    def _on_acknowledgement_finished(self) -> None:
        if self.phase != "acknowledging":
            return
        print("Wake acknowledgement completed", flush=True)
        self.audio_controller.set_mode(AudioMode.IDLE)
        self._start_command_listening()

    def _start_command_listening(self) -> None:
        if self.state_manager.current_state is not PresenceState.READY:
            self._stabilize_after_error("Command listening could not start.")
            return
        self.phase = "command"
        if not self.voice_manager.start_listening():
            self._stabilize_after_error("Voice recognizer could not start.")
            return
        print("Command listening started", flush=True)
        self.status_changed.emit("command listening")
        self._command_deadline = time.monotonic() + self.config.wake_command_timeout_seconds
        self._command_timer.start(max(1, round(self.config.wake_command_timeout_seconds * 1000)))
        print("Command timeout started", flush=True)

    def _on_command_recognized(self, text: str) -> None:
        if self.phase != "command":
            return
        self._command_timer.stop()
        self._command_deadline = 0.0
        self.phase = "conversation"

    def _command_timeout(self) -> None:
        if self.phase != "command":
            return
        print("Command timeout expired", flush=True)
        self.status_changed.emit("No command detected. Returning to sleep.")
        self.phase = "command_failed"
        self.voice_manager.cancel()
        if self.state_manager.current_state is PresenceState.READY:
            self._return_to_sleep()

    def _on_voice_error(self, message: str) -> None:
        if self.phase == "acknowledging":
            self.audio_controller.set_mode(AudioMode.IDLE)
            self._start_command_listening()
        elif self.handling_wake:
            self.phase = "command_failed"

    def _return_to_sleep(self) -> None:
        self._sleep_timer.stop()
        self._command_timer.stop()
        self._command_deadline = 0.0
        if not self.config.return_to_sleep_after_response:
            self.handling_wake = False
            self.phase = "idle"
            return
        if self.state_manager.current_state is not PresenceState.READY:
            return
        print("Returning to sleep", flush=True)
        self.handling_wake = False
        self.phase = "idle"
        if self.state_manager.transition_to(PresenceState.SLEEP):
            print("Wake monitoring resumed", flush=True)

    def force_sleep(self) -> None:
        self.voice_manager.cancel()
        self.handling_wake = False
        self.phase = "idle"
        if self.state_manager.current_state is PresenceState.READY:
            self.state_manager.transition_to(PresenceState.SLEEP)
        elif self.state_manager.current_state is not PresenceState.SLEEP:
            self.state_manager.transition_to_for_development(PresenceState.SLEEP)

    def force_wake_sequence(self) -> None:
        if self.state_manager.current_state is not PresenceState.SLEEP:
            self.force_sleep()
        self._start_monitoring()
        self.simulate(1.0)

    def _on_backend_error(self, message: str) -> None:
        self.error.emit(message)
        if isinstance(self.backend, DevelopmentWakeBackend):
            self.stop()
            return
        self._stop_monitoring()
        self.backend = DevelopmentWakeBackend()
        self.detector = WakeDetector(self.backend, self.config)
        self._connect_detector()
        self.backend_changed.emit(self.backend_name)
        self.status_changed.emit("production backend failed; development fallback active")
        if self.running and self._state_allows_monitoring():
            self._start_monitoring()

    def _stabilize_after_error(self, message: str) -> None:
        self.error.emit(message)
        self.handling_wake = False
        self.phase = "idle"
        if self.state_manager.current_state is not PresenceState.SLEEP:
            self.state_manager.transition_to_for_development(PresenceState.SLEEP)
        self._start_monitoring()

    def _emit_remaining_times(self) -> None:
        self.cooldown_changed.emit(self.cooldown_remaining)
        self.command_timeout_changed.emit(self.command_timeout_remaining)

    def shutdown(self) -> None:
        self.shutting_down = True
        self.stop()
        self.backend.shutdown()
