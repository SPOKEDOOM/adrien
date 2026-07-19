from __future__ import annotations

import logging
import threading
import time
from dataclasses import replace
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Signal

from app.ai.ai_config import AIConfig
from app.ai.ai_response import AIResponse
from app.ai.backend_status import BackendHealth, BackendState
from app.ai.errors import DuplicateRequestError, RequestCancelledError
from app.ai.hybrid_router import HybridRouter

logger = logging.getLogger(__name__)


class AIBackendManager(QObject):
    request_started = Signal(str)
    backend_selected = Signal(str)
    fallback_started = Signal(str, str)
    response_ready = Signal(object)
    request_failed = Signal(str)
    status_changed = Signal(object)
    request_cancelled = Signal(str)

    def __init__(self, config: AIConfig | None = None, router: HybridRouter | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.config = config or AIConfig()
        self.router = router or HybridRouter()
        self.backends = {}
        self.statuses: dict[str, BackendHealth] = {}
        self._lock = threading.Lock()
        self._active_request_id: str | None = None
        self._cancelled_request_ids: set[str] = set()
        self.last_response: AIResponse | None = None

    def register_backend(self, backend) -> None:
        name = backend.backend_name
        self.backends[name] = backend
        self.statuses[name] = BackendHealth(name=name, current_model=getattr(backend, "model_name", ""))
        self._emit_status()

    def initialize(self) -> None:
        for name, backend in self.backends.items():
            health = self.statuses[name]; health.status = BackendState.INITIALIZING; self._emit_status()
            try:
                backend.initialize()
                health.status = BackendState.AVAILABLE if backend.is_available() else BackendState.UNAVAILABLE
                health.last_error = "" if health.status is BackendState.AVAILABLE else "Backend unavailable"
            except Exception as exc:
                health.status = BackendState.ERROR; health.record_failure(str(exc))
            health.last_health_check = datetime.now(timezone.utc)
            self._emit_status()

    def shutdown(self) -> None:
        self.cancel_current_request()
        for name, backend in self.backends.items():
            self.statuses[name].status = BackendState.SHUTTING_DOWN
            try: backend.shutdown()
            except Exception as exc: self.statuses[name].record_failure(str(exc))
            self.statuses[name].status = BackendState.UNAVAILABLE
        self._emit_status()

    def health_check(self, name: str) -> bool:
        backend = self.backends.get(name)
        if backend is None: return False
        health = self.statuses[name]
        try:
            available = bool(backend.health_check())
            health.status = BackendState.AVAILABLE if available else BackendState.UNAVAILABLE
            health.last_error = "" if available else "Backend unavailable"
        except Exception as exc:
            available = False; health.status = BackendState.ERROR; health.record_failure(str(exc))
        health.last_health_check = datetime.now(timezone.utc)
        print(f"Backend health status changed: {name} -> {health.status.name}", flush=True)
        self._emit_status(); return available

    def generate_reply(self, request) -> AIResponse:
        with self._lock:
            if self._active_request_id is not None:
                raise DuplicateRequestError("Another AI request is already active.")
            self._active_request_id = request.request_id
            self._cancelled_request_ids.discard(request.request_id)
        started = time.monotonic(); deadline = started + request.timeout_seconds
        failed = []; previous = ""
        print(f"AI request started: {request.request_id}", flush=True)
        print(f"Hybrid mode: {self.config.hybrid_mode}", flush=True)
        self.request_started.emit(request.request_id)
        try:
            routes = self.router.route(request, self.config)
            if not routes: return self._failure(request, "No permitted AI backend is available.", started, failed)
            for index, name in enumerate(routes):
                if request.request_id in self._cancelled_request_ids: raise RequestCancelledError("AI request cancelled.")
                if time.monotonic() >= deadline:
                    print("AI request timed out", flush=True); failed.append(name); continue
                if previous:
                    print(f"Fallback: {previous} -> {name}", flush=True)
                    self.fallback_started.emit(previous, name)
                previous = name
                print(f"Attempting backend: {name}", flush=True)
                backend = self.backends.get(name)
                health = self.statuses.get(name)
                if backend is None or health is None or not backend.is_available():
                    print(f"Backend unavailable: {name}", flush=True); failed.append(name)
                    if health: health.status = BackendState.UNAVAILABLE
                    continue
                self.backend_selected.emit(name); health.status = BackendState.BUSY; self._emit_status()
                attempt = time.monotonic()
                try:
                    response = backend.generate_reply(request)
                    elapsed_attempt = time.monotonic() - attempt
                    if request.request_id in self._cancelled_request_ids: raise RequestCancelledError("AI request cancelled.")
                    if time.monotonic() >= deadline: raise TimeoutError("Backend timed out.")
                    if not isinstance(response, AIResponse) or not response.success or not response.reply_text.strip():
                        raise ValueError("Backend returned an invalid response.")
                    health.record_success(elapsed_attempt); health.status = BackendState.AVAILABLE
                    final = replace(response, processing_time=time.monotonic() - started,
                                    fallback_used=index > 0 or bool(failed),
                                    metadata={**response.metadata, "failed_backends": tuple(failed)})
                    self.last_response = final; self.response_ready.emit(final); self._emit_status()
                    print("AI response completed", flush=True); return final
                except RequestCancelledError: raise
                except Exception as exc:
                    failed.append(name); health.record_failure(str(exc)); health.status = BackendState.ERROR
                    self._emit_status(); continue
            return self._failure(request, "No AI backend could complete the request.", started, failed)
        except RequestCancelledError as exc:
            response = self._failure(request, str(exc), started, failed, emit_failure=False)
            self.request_cancelled.emit(request.request_id); print("AI request cancelled", flush=True)
            return response
        finally:
            with self._lock:
                if self._active_request_id == request.request_id: self._active_request_id = None
                self._cancelled_request_ids.discard(request.request_id)

    def _failure(self, request, message, started, failed, emit_failure=True):
        response = AIResponse(request.request_id, "", "", success=False, error_message=message,
                              processing_time=time.monotonic() - started,
                              fallback_used=bool(failed), metadata={"failed_backends": tuple(failed)})
        self.last_response = response
        if emit_failure: self.request_failed.emit(message)
        return response

    def cancel_current_request(self) -> bool:
        with self._lock:
            request_id = self._active_request_id
            if request_id is not None:
                self._cancelled_request_ids.add(request_id)
                self._active_request_id = None
        if request_id is None: return False
        for backend in self.backends.values():
            try: backend.cancel_current_request()
            except Exception: logger.exception("Backend cancellation failed")
        return True

    def status_snapshot(self) -> dict:
        return {name: health for name, health in self.statuses.items()}

    def _emit_status(self): self.status_changed.emit(self.status_snapshot())
