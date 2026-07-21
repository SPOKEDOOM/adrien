from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal

from app.ai import AIBackendManager, AIConfig, AIRequest, ProviderCredentialService
from app.ai.errors import ProviderError
from app.ai.backends import (
    LegacyConversationBackendAdapter, LocalBackend, OpenAIBackend, GroqBackend, PlaceholderAIBackend,
)
from app.conversation.conversation_config import ConversationConfig
from app.conversation.conversation_context import ConversationContext
from app.personality import PersonalityManager, PromptBuilder


class ConversationManager(QObject):
    reply_ready = Signal(str)
    processing_started = Signal(str)
    processing_finished = Signal()
    error = Signal(str)
    diagnostics_changed = Signal(object)
    openai_test_finished = Signal(object)
    groq_test_finished = Signal(object)
    _worker_succeeded = Signal(int, str, object, float)
    _worker_failed = Signal(int, str, float)

    def __init__(self, config: ConversationConfig | None = None, backend=None,
                 parent: QObject | None = None, ai_manager: AIBackendManager | None = None,
                 ai_config: AIConfig | None = None, personality_manager: PersonalityManager | None = None,
                 credential_service: ProviderCredentialService | None = None) -> None:
        super().__init__(parent)
        self.config = config or ConversationConfig()
        self.context = ConversationContext(self.config.maximum_history)
        self.personality_manager = personality_manager or PersonalityManager(parent=self)
        self.prompt_builder = PromptBuilder(self.personality_manager.trait_registry)
        self.credential_service = credential_service or ProviderCredentialService(
            cloud_enabled=(ai_config.cloud_backend_enabled if ai_config else True)
        )
        self.backend = backend  # Compatibility reference for existing replaceable providers.
        self.ai_manager = ai_manager or self._build_ai_manager(backend, ai_config)
        self.last_user_input = ""
        self.last_reply = ""
        self.last_processing_seconds = 0.0
        self.last_backend_used = ""
        self.fallback_used = False
        self.failed_backends: tuple[str, ...] = ()
        self.last_error = ""
        self.backend_status = "initializing"
        self._generation = 0
        self._worker: threading.Thread | None = None
        self._workers: set[threading.Thread] = set()
        self._workers_lock = threading.Lock()
        self._active_generation: int | None = None
        self._shutdown = False
        self._legacy_backend_name = getattr(backend, "name", "") if backend else ""
        self._worker_succeeded.connect(self._finish_success)
        self._worker_failed.connect(self._finish_failure)
        self.ai_manager.status_changed.connect(lambda statuses: self._emit_diagnostics())
        self.personality_manager.personality_changed.connect(lambda profile: self._emit_diagnostics())
        self.personality_manager.error.connect(self.error)
        self.ai_manager.initialize()
        self.backend_status = "ready"
        self._emit_diagnostics()

    def _build_ai_manager(self, backend, ai_config):
        if backend is not None:
            config = ai_config or AIConfig(hybrid_mode="placeholder_only", fallback_enabled=False)
            manager = AIBackendManager(config)
            manager.register_backend(LegacyConversationBackendAdapter(backend))
            return manager
        config = ai_config or AIConfig(request_timeout_seconds=self.config.processing_timeout_seconds)
        self.credential_service.cloud_enabled = config.cloud_backend_enabled
        resolved = self.credential_service.refresh()
        openai_config = resolved["openai"]
        groq_config = resolved["groq"]
        manager = AIBackendManager(config, openai_config=openai_config, groq_config=groq_config)
        manager.register_backend(LocalBackend())
        manager.register_backend(GroqBackend(groq_config))
        manager.register_backend(OpenAIBackend(openai_config))
        manager.register_backend(PlaceholderAIBackend())
        return manager

    @property
    def backend_name(self) -> str:
        return self.last_backend_used or self._legacy_backend_name or "placeholder"

    @property
    def is_processing(self) -> bool:
        return self._active_generation is not None

    def process(self, text: str, *, preferred_backend: str = "auto", metadata=None) -> bool:
        normalized = text.strip()
        if not normalized or self._shutdown:
            if not normalized: self.error.emit("Please say or enter something for me to process.")
            return False
        self.cancel()
        self._generation += 1
        generation = self._generation
        self._active_generation = generation
        self.last_user_input = normalized
        self.last_error = ""
        self.backend_status = "processing"
        self.processing_started.emit(normalized)
        self._emit_diagnostics()
        request_metadata = {"privacy_level": self.ai_manager.config.default_privacy_level, **(metadata or {})}
        system_prompt = self.prompt_builder.build_prompt(
            self.personality_manager.profile, self.context,
            configuration=f"hybrid mode={self.ai_manager.config.hybrid_mode}",
            task_instructions=str(request_metadata.pop("task_instructions", "")),
        )
        request_metadata["personality"] = {
            "name": self.personality_manager.profile.name,
            "tone": self.personality_manager.profile.tone,
            "traits": self.personality_manager.profile.traits,
        }
        request = AIRequest(
            user_text=normalized, conversation_history=self.context.exchanges,
            system_prompt=system_prompt,
            preferred_backend=self._legacy_backend_name or preferred_backend,
            allow_cloud=self.ai_manager.config.allow_cloud_by_default,
            allow_local=True, timeout_seconds=self.config.processing_timeout_seconds,
            metadata=request_metadata,
        )
        self._worker = threading.Thread(
            target=self._run_backend_tracked, args=(generation, normalized, request),
            name=f"adrien-conversation-{generation}", daemon=True,
        )
        with self._workers_lock: self._workers.add(self._worker)
        self._worker.start()
        QTimer.singleShot(max(1, round(self.config.processing_timeout_seconds * 1000)),
                          lambda current=generation: self._timeout(current))
        return True

    def _run_backend_tracked(self, generation: int, text: str, request: AIRequest) -> None:
        try:
            self._run_backend(generation, text, request)
        finally:
            with self._workers_lock: self._workers.discard(threading.current_thread())

    def _run_backend(self, generation: int, text: str, request: AIRequest) -> None:
        started = time.monotonic()
        try:
            response = self.ai_manager.generate_reply(request)
            if not response.success:
                raise RuntimeError(response.error_message or "AI backend failed")
            self._worker_succeeded.emit(generation, text, response, time.monotonic() - started)
        except Exception:
            self._worker_failed.emit(generation, "I could not process that request.", time.monotonic() - started)

    def _finish_success(self, generation: int, text: str, response, elapsed: float) -> None:
        if generation != self._active_generation or self._shutdown:
            print("Stale AI response ignored", flush=True); return
        self._active_generation = None
        self.last_reply = response.reply_text
        self.last_processing_seconds = response.processing_time or elapsed
        self.last_backend_used = response.backend_used
        self.fallback_used = response.fallback_used
        self.failed_backends = tuple(response.metadata.get("failed_backends", ()))
        self.backend_status = "ready"
        self.context.add_exchange(text, response.reply_text)
        self.processing_finished.emit(); self._emit_diagnostics(); self.reply_ready.emit(response.reply_text)

    def _finish_failure(self, generation: int, friendly: str, elapsed: float) -> None:
        if generation != self._active_generation or self._shutdown: return
        self._active_generation = None
        self.last_processing_seconds = elapsed; self.backend_status = "error"; self.last_error = friendly
        self.error.emit(friendly); self.processing_finished.emit(); self._emit_diagnostics(); self.reply_ready.emit(friendly)

    def _timeout(self, generation: int) -> None:
        if generation != self._active_generation or self._shutdown: return
        self.ai_manager.cancel_current_request()
        self._active_generation = None; self.backend_status = "timed out"
        friendly = "That request took too long, so I stopped waiting."
        self.last_error = friendly; self.error.emit(friendly); self.processing_finished.emit()
        self._emit_diagnostics(); self.reply_ready.emit(friendly)

    def _emit_diagnostics(self) -> None:
        self.diagnostics_changed.emit(self.diagnostics_snapshot())

    def diagnostics_snapshot(self) -> dict:
        statuses = {name: health.status.name.lower() for name, health in self.ai_manager.status_snapshot().items()}
        openai = self.ai_manager.backends.get("openai")
        openai_config = getattr(openai, "config", None)
        response_id = getattr(openai, "last_response_id", "")
        groq = self.ai_manager.backends.get("groq")
        groq_config = getattr(groq, "config", None)
        groq_response_id = getattr(groq, "last_response_id", "")
        return {
            "backend": self.backend_name, "last_user_input": self.last_user_input,
            "last_reply": self.last_reply, "conversation_count": self.context.interaction_count,
            "processing_seconds": self.last_processing_seconds, "backend_status": self.backend_status,
            "hybrid_mode": self.ai_manager.config.hybrid_mode,
            "selected_backend": self.last_backend_used or "none", "fallback_used": self.fallback_used,
            "failed_backends": self.failed_backends, "backend_statuses": statuses,
            "last_error": self.last_error,
            "personality": self.personality_manager.profile.name,
            "cloud_ai": "allowed" if self.ai_manager.config.allow_cloud_ai else "disabled",
            "openai_model": getattr(openai, "model_name", "") or "not configured",
            "openai_api_key": "configured" if getattr(openai_config, "api_key_present", False) else "missing",
            "openai_environment_detected": "yes" if getattr(openai_config, "environment_detected", False) else "no",
            "openai_sdk_installed": "yes" if getattr(openai, "sdk_installed", False) else "no",
            "openai_backend_enabled": "yes" if getattr(openai_config, "enabled", False) else "no",
            "openai_response_id": (response_id[:12] + "…") if len(response_id) > 12 else (response_id or "—"),
            "openai_latency": getattr(openai, "last_latency", 0.0),
            "openai_usage": dict(getattr(openai, "last_usage", {})),
            "openai_error_category": getattr(openai, "last_error_category", "") or "—",
            "groq_model": getattr(groq, "model_name", "") or "not configured",
            "groq_api_key": "configured" if getattr(groq_config, "api_key_present", False) else "missing",
            "groq_environment_detected": "yes" if getattr(groq_config, "environment_detected", False) else "no",
            "groq_sdk_installed": "yes" if getattr(groq, "sdk_installed", False) else "no",
            "groq_backend_enabled": "yes" if getattr(groq_config, "enabled", False) else "no",
            "groq_response_id": (groq_response_id[:12] + "…") if len(groq_response_id) > 12 else (groq_response_id or "—"),
            "groq_latency": getattr(groq, "last_latency", 0.0),
            "groq_usage": dict(getattr(groq, "last_usage", {})),
            "groq_error": " / ".join(filter(None, (
                getattr(groq, "last_error_category", ""), getattr(groq, "last_error_code", "")))) or "—",
            "openai_key_source": self.credential_service.get_provider_key_source("openai"),
            "openai_key_preview": self.credential_service.mask_secret(
                self.credential_service.get_provider_key("openai")),
            "groq_key_source": self.credential_service.get_provider_key_source("groq"),
            "groq_key_preview": self.credential_service.mask_secret(
                self.credential_service.get_provider_key("groq")),
        }

    def refresh_provider_configuration(self) -> None:
        resolved = self.credential_service.refresh()
        for name in ("groq", "openai"):
            backend = self.ai_manager.backends.get(name)
            if backend is None:
                continue
            backend.cancel_current_request()
            backend._client = None
            backend.config = resolved[name]
            backend.model_name = resolved[name].model
            if name == "groq":
                self.ai_manager.groq_config = resolved[name]
            else:
                self.ai_manager.openai_config = resolved[name]
            backend.initialize()
            self.ai_manager.health_check(name)
        self._emit_diagnostics()

    def set_hybrid_mode(self, mode: str) -> bool:
        if mode not in self.ai_manager.router.MODES: return False
        self.ai_manager.config.hybrid_mode = mode; self._emit_diagnostics(); return True

    def set_cloud_ai_allowed(self, allowed: bool) -> None:
        self.ai_manager.config.allow_cloud_ai = bool(allowed)
        self._emit_diagnostics()

    def test_backend(self, name: str) -> bool:
        return self.ai_manager.health_check(name)

    def test_openai_connection(self) -> bool:
        backend = self.ai_manager.backends.get("openai")
        if not self.ai_manager.config.allow_cloud_ai:
            self.openai_test_finished.emit({"success": False, "category": "disabled",
                                            "message": "Cloud AI is disabled."})
            return False
        if backend is not None and not getattr(backend.config, "api_key_present", False):
            self.openai_test_finished.emit({"success": False, "category": "missing_key",
                                            "message": "OpenAI API key is not configured."})
            return False
        if backend is not None and not getattr(backend, "sdk_installed", False):
            self.openai_test_finished.emit({"success": False, "category": "sdk_missing",
                                            "message": "OpenAI SDK is not installed."})
            return False
        if backend is None or not backend.is_available():
            self.openai_test_finished.emit({"success": False, "category": "unavailable",
                                            "message": "OpenAI is unavailable or not configured."})
            return False
        request = AIRequest(
            user_text="Reply with exactly: ADRIEN OpenAI connection successful.",
            system_prompt="Follow the user's formatting instruction exactly.",
            preferred_backend="openai", allow_local=False,
            allow_cloud=self.ai_manager.config.allow_cloud_ai,
            timeout_seconds=getattr(backend.config, "timeout_seconds", 30.0),
            metadata={"diagnostic_test": True},
        )
        def run():
            try:
                response = backend.test_connection(request)
                result = {"success": True, "backend": response.backend_used,
                          "model": response.model_name, "elapsed": response.processing_time,
                          "text": response.reply_text}
            except ProviderError as exc:
                result = {"success": False, "category": exc.category, "message": exc.user_message}
            except Exception:
                result = {"success": False, "category": "unknown",
                          "message": "OpenAI could not complete the connection test."}
            self.openai_test_finished.emit(result); self._emit_diagnostics()
        threading.Thread(target=run, name="adrien-openai-test", daemon=True).start()
        return True

    def test_groq_connection(self) -> bool:
        backend = self.ai_manager.backends.get("groq")
        if not self.ai_manager.config.allow_cloud_ai:
            self.groq_test_finished.emit({"success": False, "category": "disabled", "message": "Cloud AI is disabled."}); return False
        if backend is not None and not getattr(backend.config, "api_key_present", False):
            self.groq_test_finished.emit({"success": False, "category": "missing_key", "message": "Groq API key is not configured."}); return False
        if backend is not None and not getattr(backend, "sdk_installed", False):
            self.groq_test_finished.emit({"success": False, "category": "sdk_missing", "message": "Groq SDK is not installed."}); return False
        if backend is None or not backend.is_available():
            self.groq_test_finished.emit({"success": False, "category": "unavailable", "message": "Groq is unavailable or not configured."}); return False
        request = AIRequest(user_text="Reply with exactly: ADRIEN Groq connection successful.",
                            system_prompt="Follow the user's formatting instruction exactly.",
                            preferred_backend="groq", allow_local=False, allow_cloud=True,
                            timeout_seconds=backend.config.timeout_seconds,
                            metadata={"diagnostic_test": True})
        def run():
            try:
                response = backend.test_connection(request)
                result = {"success": True, "backend": response.backend_used, "model": response.model_name,
                          "elapsed": response.processing_time, "text": response.reply_text,
                          "usage": response.metadata.get("usage", {})}
            except ProviderError as exc:
                result = {"success": False, "category": exc.category, "code": exc.provider_code,
                          "message": exc.user_message}
            except Exception:
                result = {"success": False, "category": "unknown", "message": "Groq could not complete the connection test."}
            self.groq_test_finished.emit(result); self._emit_diagnostics()
        threading.Thread(target=run, name="adrien-groq-test", daemon=True).start(); return True

    def reload_personality(self) -> bool:
        return self.personality_manager.reload()

    def preview_system_prompt(self) -> str:
        return self.prompt_builder.build_prompt(
            self.personality_manager.profile, self.context,
            configuration=f"hybrid mode={self.ai_manager.config.hybrid_mode}",
        )

    def shutdown(self) -> None:
        self.cancel(); self._shutdown = True; self._generation += 1
        with self._workers_lock: workers = tuple(self._workers)
        deadline = time.monotonic() + 2.0
        for worker in workers:
            remaining = max(0.0, deadline - time.monotonic())
            if worker.is_alive() and worker is not threading.current_thread(): worker.join(timeout=remaining)
        self.ai_manager.shutdown(); self.backend_status = "stopped"

    def cancel(self) -> None:
        self.ai_manager.cancel_current_request()
        if self._active_generation is not None:
            self._generation += 1; self._active_generation = None; self.backend_status = "ready"
            self.processing_finished.emit(); self._emit_diagnostics()

    def clear_history(self) -> None:
        self.context.clear(); self.last_user_input = ""; self.last_reply = ""
        self.last_processing_seconds = 0.0; self._emit_diagnostics()
