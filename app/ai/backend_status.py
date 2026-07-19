from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto


class BackendState(Enum):
    UNINITIALIZED = auto()
    INITIALIZING = auto()
    AVAILABLE = auto()
    UNAVAILABLE = auto()
    BUSY = auto()
    ERROR = auto()
    SHUTTING_DOWN = auto()


@dataclass(slots=True)
class BackendHealth:
    name: str
    status: BackendState = BackendState.UNINITIALIZED
    last_health_check: datetime | None = None
    last_error: str = ""
    current_model: str = ""
    average_response_time: float = 0.0
    request_count: int = 0
    failure_count: int = 0

    def record_success(self, elapsed: float) -> None:
        total = self.average_response_time * self.request_count
        self.request_count += 1
        self.average_response_time = (total + elapsed) / self.request_count
        self.last_error = ""

    def record_failure(self, error: str) -> None:
        self.failure_count += 1
        self.last_error = error
