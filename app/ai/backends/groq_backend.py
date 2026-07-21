from __future__ import annotations

import asyncio
import logging
import threading
import time

from app.ai.ai_backend import AIBackend
from app.ai.ai_response import AIResponse
from app.ai.errors import BackendUnavailableError, ProviderError, RequestCancelledError
from app.ai.groq_config import GroqConfig

logger = logging.getLogger(__name__)
try:
    from groq import AsyncGroq
except ImportError:
    AsyncGroq = None


class GroqBackend(AIBackend):
    backend_name = "groq"; backend_type = "cloud"

    def __init__(self, config: GroqConfig | None = None, *, client_factory=None):
        self.config = config; self.model_name = config.model if config else ""
        self._client_factory = client_factory; self._client = None
        self._task = self._loop = None; self._lock = threading.Lock()
        self.last_response_id = ""; self.last_latency = 0.0; self.last_usage = {}
        self.last_error_category = ""; self.last_error_code = ""; self.last_status = "unavailable"

    @property
    def sdk_installed(self): return AsyncGroq is not None

    def initialize(self):
        try: self.config = self.config or GroqConfig.resolve()
        except ValueError:
            self.last_status = "error"; logger.warning("Groq configuration invalid"); return
        self.model_name = self.config.model
        logger.info("Groq configuration loaded key_configured=%s model=%s enabled=%s sdk=%s",
                    "yes" if self.config.api_key_present else "no", self.model_name,
                    "yes" if self.config.enabled else "no", "yes" if self.sdk_installed else "no")
        if not self.config.enabled: self.last_status = "disabled"; return
        if not self.config.api_key_present or (AsyncGroq is None and self._client_factory is None):
            self.last_status = "unavailable"; return
        try:
            factory = self._client_factory or AsyncGroq
            self._client = factory(api_key=self.config.api_key, timeout=self.config.timeout_seconds)
        except Exception:
            self.last_status = "error"; logger.warning("Groq client creation failed"); return
        self.last_status = "available"; logger.info("Groq backend initialized model=%s", self.model_name)

    def is_available(self): return self._client is not None and self.last_status in ("available", "degraded")
    def generate_reply(self, request): return self._generate_reply(request, self.config.max_output_tokens)
    def test_connection(self, request): return self._generate_reply(request, min(32, self.config.max_output_tokens))

    def _generate_reply(self, request, max_tokens):
        if not self.is_available(): raise BackendUnavailableError("Groq is unavailable or not configured.")
        started = time.monotonic(); logger.info("Groq request started request_id=%s model=%s", request.request_id, self.model_name)
        try:
            completion = asyncio.run(self._generate(request, max_tokens))
            text = self._extract_text(completion)
            if not text: raise ProviderError("invalid_response", "Groq returned no readable text.")
            self.last_latency = time.monotonic() - started
            self.last_response_id = str(getattr(completion, "id", "") or "")
            self.last_usage = self._extract_usage(completion); self.last_error_category = self.last_error_code = ""
            self.last_status = "available"
            choice = (getattr(completion, "choices", None) or [None])[0]
            metadata = {"response_id": self.last_response_id, "usage": dict(self.last_usage),
                        "finish_reason": str(getattr(choice, "finish_reason", "") or "")}
            logger.info("Groq request completed request_id=%s model=%s elapsed=%.3f usage=%s",
                        request.request_id, self.model_name, self.last_latency, self.last_usage)
            return AIResponse(request.request_id, text, "groq", self.model_name,
                              processing_time=self.last_latency, metadata=metadata)
        except asyncio.CancelledError as exc:
            self._record("cancelled", "", started, request.request_id, True)
            raise RequestCancelledError("AI request cancelled.") from exc
        except ProviderError as exc:
            self._record(exc.category, exc.provider_code, started, request.request_id, exc.transient); raise
        except Exception as exc:
            mapped = self._map_exception(exc)
            self._record(mapped.category, mapped.provider_code, started, request.request_id, mapped.transient)
            raise mapped from exc

    async def _generate(self, request, max_tokens):
        messages = [{"role": "system", "content": request.system_prompt}]
        for exchange in request.conversation_history:
            if exchange.user_message: messages.append({"role": "user", "content": exchange.user_message})
            if exchange.adrien_reply: messages.append({"role": "assistant", "content": exchange.adrien_reply})
        if messages[-1]["role"] != "user" or messages[-1]["content"] != request.user_text:
            messages.append({"role": "user", "content": request.user_text})
        task = asyncio.create_task(self._client.chat.completions.create(
            model=self.model_name, messages=messages, max_tokens=max_tokens))
        with self._lock: self._loop, self._task = asyncio.get_running_loop(), task
        try: return await task
        finally:
            with self._lock: self._loop = self._task = None

    def cancel_current_request(self):
        with self._lock: loop, task = self._loop, self._task
        if loop and task and not task.done(): loop.call_soon_threadsafe(task.cancel)

    def _record(self, category, code, started, request_id, transient):
        self.last_latency = time.monotonic() - started; self.last_error_category = category
        self.last_error_code = code; self.last_status = "degraded" if transient else "error"
        logger.warning("Groq request failed request_id=%s category=%s code=%s elapsed=%.3f",
                       request_id, category, code or "none", self.last_latency)

    @staticmethod
    def _extract_text(value):
        choices = getattr(value, "choices", None) or []
        message = getattr(choices[0], "message", None) if choices else None
        content = getattr(message, "content", "") if message else ""
        return content.strip() if isinstance(content, str) else ""

    @staticmethod
    def _extract_usage(value):
        usage = getattr(value, "usage", None); result = {}
        mapping = {"prompt_tokens": "input_tokens", "completion_tokens": "output_tokens", "total_tokens": "total_tokens"}
        for source, target in mapping.items():
            token_count = getattr(usage, source, None) if usage else None
            if isinstance(token_count, int): result[target] = token_count
        return result

    @staticmethod
    def _map_exception(exc):
        name = type(exc).__name__; status = getattr(exc, "status_code", None)
        body = getattr(exc, "body", None) or {}; error = body.get("error", body) if isinstance(body, dict) else {}
        code = str(error.get("code", "") or "") if isinstance(error, dict) else ""
        lower_code = code.lower()
        if "quota" in lower_code: category, message, transient = "quota", "Groq quota is unavailable for this request.", True
        elif name == "AuthenticationError" or status == 401: category, message, transient = "authentication", "Groq authentication failed. Check the configured API key.", False
        elif name == "PermissionDeniedError" or status == 403: category, message, transient = "permission", "Groq denied permission for this request.", False
        elif name == "RateLimitError" or status == 429: category, message, transient = "rate_limit", "Groq is temporarily rate-limited. ADRIEN will try another backend.", True
        elif name == "APITimeoutError": category, message, transient = "timeout", "Groq did not respond before the request timed out.", True
        elif name == "APIConnectionError": category, message, transient = "connection", "ADRIEN could not reach Groq.", True
        elif name == "NotFoundError" or status == 404 or "model" in lower_code: category, message, transient = "model_not_found", "The configured Groq model is unavailable.", False
        elif name in ("BadRequestError", "UnprocessableEntityError") or isinstance(status, int) and 400 <= status < 500: category, message, transient = "invalid_request", "Groq could not accept this request.", False
        elif name == "InternalServerError" or isinstance(status, int) and status >= 500: category, message, transient = "server", "Groq is temporarily unavailable.", True
        else: category, message, transient = "unknown", "Groq could not complete the request.", False
        return ProviderError(category, message, transient=transient, provider_code=code, http_status=status)
