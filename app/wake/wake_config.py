from dataclasses import dataclass


@dataclass(slots=True)
class WakeConfig:
    wake_enabled: bool = True
    wake_phrase: str = "Adrien"
    wake_backend: str = "development"
    wake_confidence_threshold: float = 0.75
    wake_cooldown_seconds: float = 2.0
    wake_decision_delay_ms: int = 200
    wake_materialization_duration_ms: int = 700
    wake_acknowledgement_enabled: bool = False
    wake_acknowledgement_text: str = "Yes?"
    wake_command_timeout_seconds: float = 8.0
    return_to_sleep_after_response: bool = True
    ready_before_sleep_seconds: float = 1.0
    wake_debug_controls: bool = True
    wake_allow_during_ready: bool = False
    sample_rate: int = 16_000
    frame_size: int = 1_280
    ring_buffer_seconds: float = 2.0
    debug: bool = True
