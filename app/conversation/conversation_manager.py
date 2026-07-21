from __future__ import annotations

import threading
import time
import re
from uuid import uuid4

from PySide6.QtCore import QObject, QTimer, Signal

from app.ai import AIBackendManager, AIConfig, AIRequest, ProviderCredentialService
from app.ai.errors import ProviderError
from app.ai.backends import (
    LegacyConversationBackendAdapter, LocalBackend, OpenAIBackend, GroqBackend, PlaceholderAIBackend,
)
from app.conversation.conversation_config import ConversationConfig
from app.conversation.conversation_context import ConversationContext
from app.conversation.conversation_memory import ConversationMemory
from app.personality import PersonalityManager, PromptBuilder
from app.memory import LongTermMemoryManager


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
    _summary_ready = Signal(int, str, object)
    _summary_failed = Signal(int)

    def __init__(self, config: ConversationConfig | None = None, backend=None,
                 parent: QObject | None = None, ai_manager: AIBackendManager | None = None,
                 ai_config: AIConfig | None = None, personality_manager: PersonalityManager | None = None,
                 credential_service: ProviderCredentialService | None = None,
                 long_term_memory: LongTermMemoryManager | None = None) -> None:
        super().__init__(parent)
        self.config = config or ConversationConfig()
        self.context = ConversationMemory(
            self.config.maximum_recent_messages, self.config.summary_threshold,
            self.config.maximum_summary_words, self.config.conversation_summaries_enabled,
        )
        self.memory = self.context
        self.session_id = str(uuid4())
        self.long_term_memory = long_term_memory or LongTermMemoryManager()
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
        self._memory_generation = 0
        self._shutdown = False
        self._legacy_backend_name = getattr(backend, "name", "") if backend else ""
        self._worker_succeeded.connect(self._finish_success)
        self._worker_failed.connect(self._finish_failure)
        self._summary_ready.connect(self._finish_summary)
        self._summary_failed.connect(self._fail_summary)
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
        memory_reply = self._handle_memory_command(normalized)
        if memory_reply is not None:
            self._complete_memory_command(normalized, memory_reply)
            return True
        if normalized.casefold().startswith(("what is my ", "what's my ", "which ")):
            matches = self.long_term_memory.search_relevant(normalized, limit=3)
            if matches:
                self._complete_memory_command(normalized, "Based on saved memory: " + "; ".join(
                    item.content for item in matches))
                return True
            self._complete_memory_command(normalized, "I don't have matching information in long-term memory.")
            return True
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
            configuration=(f"hybrid mode={self.ai_manager.config.hybrid_mode}; "
                           f"provider={self.ai_manager.config.default_backend}; session={self.session_id}"),
            task_instructions=str(request_metadata.pop("task_instructions", "")),
        )
        request_metadata["personality"] = {
            "name": self.personality_manager.profile.name,
            "tone": self.personality_manager.profile.tone,
            "traits": self.personality_manager.profile.traits,
        }
        existing_context = " ".join(
            [self.memory.summary.text if self.memory.summary else ""] +
            [f"{item.user_message} {item.adrien_reply}" for item in self.memory.exchanges]
        )
        relevant_memories = self.long_term_memory.search_relevant(normalized, exclude_text=existing_context)
        if relevant_memories:
            system_prompt += "\nRelevant Long-Term Memory:\n" + "\n".join(
                f"- [{item.category}] {item.content}" for item in relevant_memories)
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
        self._start_summary_if_needed()

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
            "memory_recent_messages": self.memory.recent_message_count,
            "memory_summary_exists": bool(self.memory.summary),
            "memory_summary_size": len(self.memory.summary.text) if self.memory.summary else 0,
            "memory_summary_updated": (self.memory.summary.last_updated_timestamp.isoformat()
                                       if self.memory.summary else "—"),
            "memory_messages_summarized": (self.memory.summary.message_count_represented
                                           if self.memory.summary else 0),
            "memory_estimated_tokens": self.memory.estimated_tokens,
            "memory_status": self.memory.status,
            **{f"long_term_{key}": value for key, value in self.long_term_memory.diagnostics().items()},
        }

    def configure_long_term_memory(self, enabled, suggestions_enabled, ask_before_saving,
                                   maximum_memories, disabled_categories=()):
        memory = self.long_term_memory; memory.enabled = bool(enabled)
        memory.suggestions_enabled = bool(suggestions_enabled)
        memory.ask_before_saving = bool(ask_before_saving)
        memory.maximum_memories = max(1, int(maximum_memories))
        memory.disabled_categories = set(disabled_categories); self._emit_diagnostics()

    def _handle_memory_command(self, text):
        lower = text.casefold().strip()
        explicit = re.match(r"^(?:remember that|save this to memory[: ]*)\s*(.+)$", text, re.I)
        if explicit:
            content = explicit.group(1).strip().rstrip(".")
            try:
                memory = self.long_term_memory.create("note", content[:60], content,
                                                      source="explicit user request", importance=4)
                return f"I'll remember that: {memory.content}."
            except ValueError as exc: return str(exc)
        if lower.startswith("forget "):
            query = re.sub(r"^forget (?:that |about )?", "", text, flags=re.I)
            matches = self.long_term_memory.search_relevant(query, limit=5)
            if not matches: return "I don't have a matching long-term memory to forget."
            for memory in matches: self.long_term_memory.delete(memory.id)
            return f"I forgot {len(matches)} matching long-term memory item{'s' if len(matches) != 1 else ''}."
        if lower.startswith("what do you remember") or lower.startswith("do you remember"):
            category = next((value for value in ("project", "goal", "preference", "identity", "tool") if value in lower), None)
            query = re.sub(r"^(what do you remember|do you remember)(?: about)?", "", text, flags=re.I)
            matches = self.long_term_memory.list(category=category) if category else self.long_term_memory.search_relevant(query or text, limit=5)
            if not matches and not query.strip(): matches = self.long_term_memory.list()[:5]
            if not matches: return "I don't have any matching long-term memory."
            return "I remember: " + "; ".join(item.content for item in matches[:5])
        candidate_match = re.search(r"\bcall me ([A-Za-z][A-Za-z -]{1,40}) from now on\b", text, re.I)
        if (candidate_match and self.long_term_memory.suggestions_enabled and
                self.long_term_memory.ask_before_saving):
            name = candidate_match.group(1).strip()
            candidate = self.long_term_memory.create_candidate("identity", "Preferred name", f"User prefers to be called {name}.")
            if candidate: return f"Would you like me to remember that you prefer to be called {name}?"
        return None

    def _complete_memory_command(self, text, reply):
        self.cancel(); self.last_user_input = text; self.last_reply = reply; self.last_backend_used = "memory"
        self.backend_status = "ready"; self.processing_started.emit(text)
        self.memory.add_exchange(text, reply); self.processing_finished.emit(); self._emit_diagnostics()
        QTimer.singleShot(0, lambda value=reply: self.reply_ready.emit(value))

    def refresh_long_term_memory_diagnostics(self): self._emit_diagnostics()
    def rebuild_long_term_memory_index(self): self.long_term_memory.rebuild_index(); self._emit_diagnostics()
    def clear_pending_memory_candidates(self): self.long_term_memory.clear_candidates(); self._emit_diagnostics()

    def configure_memory(self, maximum_recent_messages, summary_threshold,
                         maximum_summary_words, summaries_enabled):
        self.memory.maximum_recent_messages = max(2, int(maximum_recent_messages))
        self.memory.summary_threshold = max(2, int(summary_threshold))
        self.memory.maximum_summary_words = max(20, int(maximum_summary_words))
        self.memory.summaries_enabled = bool(summaries_enabled); self._emit_diagnostics()

    def _start_summary_if_needed(self, *, force=False):
        represented = self.memory.summary_candidates(force=force)
        if not represented: return False
        self._emit_diagnostics()
        generation = self._memory_generation
        worker = threading.Thread(target=self._generate_summary_tracked,
                                  args=(generation, represented),
                                  name="adrien-memory-summary", daemon=True)
        with self._workers_lock: self._workers.add(worker)
        worker.start()
        return True

    def force_summary(self): return self._start_summary_if_needed(force=True)

    def _generate_summary_tracked(self, generation, represented):
        try: self._generate_summary(generation, represented)
        finally:
            with self._workers_lock: self._workers.discard(threading.current_thread())

    def _generate_summary(self, generation, represented):
        try:
            transcript = "\n".join(
                f"User: {item.user_message}\nADRIEN: {item.adrien_reply}" for item in represented)
            request = AIRequest(
                user_text=("Summarize this conversation compactly. Preserve goals, decisions, user requests, "
                           f"commitments, project state, open questions and unfinished work.\n{transcript}"),
                system_prompt="Create a factual conversation-memory summary. Do not add new facts.",
                conversation_history=(), timeout_seconds=self.config.processing_timeout_seconds,
                allow_cloud=self.ai_manager.config.allow_cloud_ai,
                metadata={"memory_summary": True},
            )
            routes = self.ai_manager.router.route(request, self.ai_manager.config)
            text = ""
            for name in routes:
                backend = self.ai_manager.backends.get(name)
                if name not in ("groq", "openai") or backend is None or not backend.is_available(): continue
                try:
                    response = backend.generate_reply(request)
                    if response.success: text = response.reply_text; break
                except Exception: continue
            if not text: text = self.memory.deterministic_summary(represented)
            self._summary_ready.emit(generation, text, represented)
        except Exception:
            self._summary_failed.emit(generation)

    def _finish_summary(self, generation, text, represented):
        if self._shutdown or generation != self._memory_generation: return
        self.memory.apply_summary(text, represented); self._emit_diagnostics()

    def _fail_summary(self, generation):
        if generation != self._memory_generation: return
        self.memory.summary_failed(); self._emit_diagnostics()

    def clear_conversation_memory(self):
        self.clear_history()

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
        self._memory_generation += 1
        self.context.clear(); self.last_user_input = ""; self.last_reply = ""
        self.last_processing_seconds = 0.0; self._emit_diagnostics()
