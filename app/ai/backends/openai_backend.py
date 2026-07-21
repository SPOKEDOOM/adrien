from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

from app.ai.ai_backend import AIBackend
from app.ai.ai_response import AIResponse
from app.ai.errors import BackendUnavailableError, ProviderError, RequestCancelledError
from app.ai.openai_config import OpenAIConfig

logger = logging.getLogger(__name__)

try:
    import openai as _openai
    from openai import AsyncOpenAI
except ImportError:  # ADRIEN must still launch without optional cloud support.
    _openai = None
    AsyncOpenAI = None


class OpenAIBackend(AIBackend):
    backend_name = "openai"
    backend_type = "cloud"

    def __init__(self, config: OpenAIConfig | None = None, *, client_factory=None):
        self.config = config
        self.model_name = config.model if config else ""
        self._client_factory = client_factory
        self._client = None
        self._task = None
        self._loop = None
        self._lock = threading.Lock()
        self.last_response_id = ""
        self.last_latency = 0.0
        self.last_usage: dict[str, int] = {}
        self.last_error_category = ""
        self.last_status = "unavailable"

    def initialize(self) -> None:
        try:
            self.config = self.config or OpenAIConfig.from_environment()
        except ValueError:
            self.last_status = "error"
            logger.warning("OpenAI initialization failed: invalid configuration")
            return
        self.model_name = self.config.model
        configuration_message = (
            "OpenAI configuration: "
            f"key_configured={'yes' if self.config.api_key_present else 'no'}, "
            f"model={self.model_name}, enabled={'yes' if self.config.enabled else 'no'}"
        )
        print(configuration_message, flush=True)
        logger.info(configuration_message)
        if not self.config.enabled:
            self.last_status = "disabled"; return
        if not self.config.api_key_present:
            self.last_status = "unavailable"; return
        if AsyncOpenAI is None and self._client_factory is None:
            self.last_status = "unavailable"; return
        factory = self._client_factory or AsyncOpenAI
        try:
            kwargs = {"timeout": self.config.timeout_seconds}
            if self.config.api_key:
                kwargs["api_key"] = self.config.api_key
            self._client = factory(**kwargs)
        except Exception:
            self._client = None; self.last_status = "error"
            logger.warning("OpenAI client creation failed")
            return
        self.last_status = "available"
        logger.info("OpenAI backend initialized model=%s", self.model_name)

    @property
    def sdk_installed(self) -> bool:
        return AsyncOpenAI is not None

    def is_available(self) -> bool:
        return self._client is not None and self.last_status in ("available", "degraded")

    def generate_reply(self, request) -> AIResponse:
        return self._generate_reply(request, self.config.max_output_tokens)

    def test_connection(self, request) -> AIResponse:
        """Explicit paid connection check; callers must only invoke on user action."""
        return self._generate_reply(request, min(32, self.config.max_output_tokens))

    def _generate_reply(self, request, max_tokens: int) -> AIResponse:
        if not self.is_available():
            raise BackendUnavailableError("OpenAI is unavailable or not configured.")
        started = time.monotonic()
        logger.info("OpenAI request started request_id=%s model=%s", request.request_id, self.model_name)
        try:
            response = asyncio.run(self._generate(request, max_tokens))
            text = self._extract_text(response)
            if not text:
                raise ProviderError("invalid_response", "OpenAI returned no readable text.")
            self.last_latency = time.monotonic() - started
            self.last_response_id = str(getattr(response, "id", "") or "")
            self.last_usage = self._extract_usage(response)
            self.last_error_category = ""; self.last_status = "available"
            metadata = {
                "response_id": self.last_response_id, "status": getattr(response, "status", ""),
                "usage": dict(self.last_usage), "finish_reason": self._finish_reason(response),
            }
            logger.info("OpenAI request completed request_id=%s model=%s elapsed=%.3f usage=%s",
                        request.request_id, self.model_name, self.last_latency, self.last_usage)
            return AIResponse(request.request_id, text, self.backend_name, self.model_name,
                              processing_time=self.last_latency, metadata=metadata)
        except asyncio.CancelledError as exc:
            self._record_error("cancelled", started, request.request_id, transient=True)
            raise RequestCancelledError("AI request cancelled.") from exc
        except RequestCancelledError:
            self._record_error("cancelled", started, request.request_id, transient=True); raise
        except ProviderError as exc:
            self._record_error(exc.category, started, request.request_id, transient=exc.transient); raise
        except Exception as exc:
            mapped = self._map_exception(exc)
            self._record_error(mapped.category, started, request.request_id, transient=mapped.transient)
            raise mapped from exc

    async def _generate(self, request, max_tokens: int):
        messages = []
        for exchange in request.conversation_history:
            user = getattr(exchange, "user_message", "")
            assistant = getattr(exchange, "adrien_reply", "")
            if user: messages.append({"role": "user", "content": user})
            if assistant: messages.append({"role": "assistant", "content": assistant})
        if not messages or messages[-1].get("content") != request.user_text or messages[-1].get("role") != "user":
            messages.append({"role": "user", "content": request.user_text})
        task = asyncio.create_task(self._client.responses.create(
            model=self.model_name, instructions=request.system_prompt, input=messages,
            max_output_tokens=max_tokens,
        ))
        with self._lock: self._loop, self._task = asyncio.get_running_loop(), task
        try:
            return await task
        finally:
            with self._lock: self._loop, self._task = None, None

    def cancel_current_request(self) -> None:
        with self._lock: loop, task = self._loop, self._task
        if loop and task and not task.done(): loop.call_soon_threadsafe(task.cancel)

    def _record_error(self, category: str, started: float, request_id: str, *, transient: bool) -> None:
        self.last_latency = time.monotonic() - started
        self.last_error_category = category
        self.last_status = "degraded" if transient else "error"
        logger.warning("OpenAI request failed request_id=%s category=%s elapsed=%.3f",
                       request_id, category, self.last_latency)

    @staticmethod
    def _extract_text(response: Any) -> str:
        convenience = getattr(response, "output_text", None)
        if isinstance(convenience, str) and convenience.strip(): return convenience.strip()
        parts = []
        for item in getattr(response, "output", ()) or ():
            for content in getattr(item, "content", ()) or ():
                if getattr(content, "type", "") in ("output_text", "text"):
                    value = getattr(content, "text", "")
                    if isinstance(value, str): parts.append(value)
        return "\n".join(parts).strip()

    @staticmethod
    def _extract_usage(response: Any) -> dict[str, int]:
        usage = getattr(response, "usage", None)
        result = {}
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = getattr(usage, key, None) if usage is not None else None
            if isinstance(value, int): result[key] = value
        return result

    @staticmethod
    def _finish_reason(response: Any) -> str:
        for item in reversed(getattr(response, "output", ()) or ()):
            reason = getattr(item, "finish_reason", None)
            if reason: return str(reason)
        return ""

    @staticmethod
    def _map_exception(exc: Exception) -> ProviderError:
        name = type(exc).__name__
        mapping = {
            "AuthenticationError": ("auth", "OpenAI authentication failed. Check the configured API key.", False),
            "PermissionDeniedError": ("permission", "OpenAI denied permission for this request.", False),
            "RateLimitError": ("rate_limit", "OpenAI is temporarily rate-limited. ADRIEN will try another available backend.", True),
            "APITimeoutError": ("timeout", "OpenAI did not respond before the request timed out.", True),
            "APIConnectionError": ("connection", "ADRIEN could not reach OpenAI.", True),
            "BadRequestError": ("invalid_request", "OpenAI could not accept this request.", False),
            "NotFoundError": ("invalid_request", "OpenAI could not accept this request.", False),
            "UnprocessableEntityError": ("invalid_request", "OpenAI could not accept this request.", False),
            "InternalServerError": ("server", "OpenAI is temporarily unavailable.", True),
        }
        category, message, transient = mapping.get(name, ("unknown", "OpenAI could not complete the request.", False))
        status = getattr(exc, "status_code", None)
        if name not in mapping and isinstance(status, int):
            if status == 401: category, message = "auth", "OpenAI authentication failed. Check the configured API key."
            elif status == 403: category, message = "permission", "OpenAI denied permission for this request."
            elif status == 429: category, message, transient = "rate_limit", "OpenAI is temporarily rate-limited. ADRIEN will try another available backend.", True
            elif status >= 500: category, message, transient = "server", "OpenAI is temporarily unavailable.", True
            elif status >= 400: category, message = "invalid_request", "OpenAI could not accept this request."
        return ProviderError(category, message, transient=transient)
