from __future__ import annotations

from collections import deque
from threading import Lock


class AudioRingBuffer:
    """Thread-safe bounded mono sample window for a future production backend."""

    def __init__(self, capacity: int):
        self.capacity = max(1, int(capacity))
        self._samples = deque(maxlen=self.capacity)
        self._lock = Lock()

    def append(self, samples) -> None:
        with self._lock:
            self._samples.extend(float(sample) for sample in samples)

    def snapshot(self) -> tuple[float, ...]:
        with self._lock:
            return tuple(self._samples)

    def clear(self) -> None:
        with self._lock:
            self._samples.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._samples)
